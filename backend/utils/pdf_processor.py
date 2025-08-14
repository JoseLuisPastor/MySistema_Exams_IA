import os
import fitz  # PyMuPDF
import re
import json
import math
import time
from dotenv import load_dotenv
from openai import OpenAI

# Cargar variables de entorno
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")

if not api_key or not base_url:
    raise ValueError("⚠ Faltan las variables OPENAI_API_KEY o OPENAI_BASE_URL en .env")

client = OpenAI(api_key=api_key, base_url=base_url)

def extract_text_from_pdf(pdf_path):
    """Extraer texto completo del PDF"""
    try:
        doc = fitz.open(pdf_path)
        pdf_text = ""
        for page in doc:
            pdf_text += page.get_text()
        doc.close()
        return pdf_text
    except Exception as e:
        print(f"❌ Error extrayendo texto del PDF: {e}")
        return ""

def extraer_preguntas(texto_completo):
    """Extraer preguntas sin incisos - versión optimizada"""
    if not texto_completo.strip():
        return []
    
    try:
        # Captura bloques desde número + punto hasta la siguiente pregunta o fin
        patron = r'(\d+\.\s.*?)(?=\n\d+\.|\Z)'
        bloques = re.findall(patron, texto_completo, re.DOTALL)
        preguntas_limpias = []
        
        for b in bloques[:100]:  # Limitar a 100 preguntas máximo
            # Quitar saltos de línea
            pregunta = " ".join(b.split())
            # Eliminar incisos (A) B) C)...) y todo lo que sigue
            pregunta = re.split(r'\s[A-E]\)', pregunta)[0]
            # Filtrar basura (muy corta o muy larga)
            if 10 < len(pregunta) < 500:  # Limitar longitud
                preguntas_limpias.append(pregunta.strip())
        
        return preguntas_limpias
    except Exception as e:
        print(f"❌ Error extrayendo preguntas: {e}")
        return []

def generate_simple_questions(tema, num_preguntas, difficulty):
    """Generar preguntas de forma más simple y rápida"""
    
    # Prompt más corto y directo
    prompt = f"""Genera {num_preguntas} preguntas de {tema} nivel {difficulty}.

FORMATO JSON OBLIGATORIO:
{{"preguntas":[{{"numero":1,"tema":"{tema}","pregunta":"...","opciones":{{"A":"...","B":"...","C":"...","D":"..."}},"respuesta_correcta":"A"}}]}}

Solo responde JSON, nada más."""

    try:
        response = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,  # Limitar tokens
            temperature=0.7
        )
        
        content = response.choices[0].message.content.strip()
        
        # Extraer JSON
        start = content.find('{"preguntas"')
        if start == -1:
            start = content.find('{')
        end = content.rfind('}') + 1
        
        if start != -1 and end > start:
            json_str = content[start:end]
            data = json.loads(json_str)
            return data.get("preguntas", [])
        
        return []
        
    except Exception as e:
        print(f"❌ Error en generate_simple_questions: {e}")
        return []

def create_basic_questions(num_preguntas, tema="Matemáticas"):
    """Crear preguntas básicas sin IA como último recurso"""
    preguntas = []
    
    ejemplos_matematicas = [
        "¿Cuál es el resultado de 2 + 2?",
        "¿Cuánto es 5 × 3?",
        "¿Cuál es el área de un cuadrado de lado 4?",
        "¿Cuánto es 100 ÷ 5?",
        "¿Cuál es el perímetro de un rectángulo de 3×4?",
    ]
    
    for i in range(num_preguntas):
        if i < len(ejemplos_matematicas):
            pregunta_texto = ejemplos_matematicas[i]
        else:
            pregunta_texto = f"Pregunta de {tema} número {i+1}"
        
        preguntas.append({
            "numero": i + 1,
            "tema": tema,
            "pregunta": pregunta_texto,
            "opciones": {
                "A": "4" if i == 0 else "15" if i == 1 else "16" if i == 2 else "20" if i == 3 else "14",
                "B": "3" if i == 0 else "12" if i == 1 else "12" if i == 2 else "15" if i == 3 else "10",
                "C": "5" if i == 0 else "18" if i == 1 else "8" if i == 2 else "25" if i == 3 else "12",
                "D": "6" if i == 0 else "20" if i == 1 else "20" if i == 2 else "30" if i == 3 else "16"
            },
            "respuesta_correcta": "A"
        })
    
    return preguntas

def generate_exam(pdf_path, num_questions=20, difficulty='medium'):
    """Generar examen - versión ultra optimizada para Render"""
    print(f"🔄 Iniciando generación de {num_questions} preguntas...")
    
    try:
        # Paso 1: Extraer preguntas del PDF (rápido)
        pdf_text = extract_text_from_pdf(pdf_path)
        preguntas_pdf = extraer_preguntas(pdf_text)
        
        print(f"📄 Extraídas {len(preguntas_pdf)} preguntas del PDF")
        
        # Determinar tema básico
        tema = "Matemáticas"  # Por defecto
        if preguntas_pdf:
            texto_muestra = " ".join(preguntas_pdf[:3]).lower()
            if "historia" in texto_muestra or "revolución" in texto_muestra:
                tema = "Historia"
            elif "biología" in texto_muestra or "célula" in texto_muestra:
                tema = "Biología"
            elif "física" in texto_muestra or "energía" in texto_muestra:
                tema = "Física"
            elif "química" in texto_muestra or "elemento" in texto_muestra:
                tema = "Química"
        
        print(f"📚 Tema identificado: {tema}")
        
        # Paso 2: Intentar generar con IA (con timeout interno)
        preguntas_finales = []
        
        if num_questions <= 3:
            # Para pocas preguntas, un solo intento
            print("⚡ Generando todas las preguntas en una llamada...")
            preguntas_ia = generate_simple_questions(tema, num_questions, difficulty)
            
            if preguntas_ia and len(preguntas_ia) > 0:
                print(f"✅ IA generó {len(preguntas_ia)} preguntas")
                preguntas_finales = preguntas_ia[:num_questions]
            else:
                print("⚠ IA falló, usando preguntas básicas")
                preguntas_finales = create_basic_questions(num_questions, tema)
        else:
            # Para más preguntas, generar solo las básicas para evitar timeout
            print("⚠ Muchas preguntas solicitadas, generando básicas para evitar timeout")
            preguntas_finales = create_basic_questions(num_questions, tema)
        
        # Paso 3: Asegurar numeración correcta
        for i, pregunta in enumerate(preguntas_finales):
            pregunta["numero"] = i + 1
        
        resultado = {"preguntas": preguntas_finales[:num_questions]}
        print(f"🎉 Examen completado: {len(resultado['preguntas'])} preguntas")
        
        return resultado
        
    except Exception as e:
        print(f"❌ Error crítico en generate_exam: {e}")
        # Último recurso: preguntas básicas
        preguntas_emergencia = create_basic_questions(min(num_questions, 5), "General")
        return {"preguntas": preguntas_emergencia}

def create_fallback_exam(preguntas_originales, num_questions):
    """Crear examen básico en caso de fallo completo de IA"""
    import random
    
    if not preguntas_originales:
        return {"preguntas": create_basic_questions(num_questions)}
    
    # Seleccionar preguntas aleatoriamente
    max_preguntas = min(num_questions, len(preguntas_originales))
    selected_questions = random.sample(preguntas_originales, max_preguntas)
    
    exam_questions = []
    opciones_ejemplo = [
        {"A": "Verdadero", "B": "Falso", "C": "Depende", "D": "No se puede determinar"},
        {"A": "Siempre", "B": "Nunca", "C": "A veces", "D": "Frecuentemente"},
        {"A": "Correcto", "B": "Incorrecto", "C": "Parcial", "D": "Completo"}
    ]
    
    for i, pregunta_texto in enumerate(selected_questions):
        opciones = opciones_ejemplo[i % len(opciones_ejemplo)]
        
        exam_questions.append({
            "numero": i + 1,
            "tema": "General",
            "pregunta": pregunta_texto[:200] + ("..." if len(pregunta_texto) > 200 else ""),
            "opciones": opciones,
            "respuesta_correcta": random.choice(["A", "B", "C", "D"])
        })
    
    return {"preguntas": exam_questions}
