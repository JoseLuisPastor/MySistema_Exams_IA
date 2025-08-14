import os
import fitz  # PyMuPDF
import re
import json
import math
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
    doc = fitz.open(pdf_path)
    pdf_text = ""
    for page in doc:
        pdf_text += page.get_text()
    doc.close()
    return pdf_text

def extraer_preguntas(texto_completo):
    """Extraer preguntas sin incisos (versión exacta del usuario)"""
    # Captura bloques desde número + punto hasta la siguiente pregunta o fin
    patron = r'(\d+\.\s.*?)(?=\n\d+\.|\Z)'
    bloques = re.findall(patron, texto_completo, re.DOTALL)
    preguntas_limpias = []
    
    for b in bloques:
        # Quitar saltos de línea
        pregunta = " ".join(b.split())
        # Eliminar incisos (A) B) C)...) y todo lo que sigue
        pregunta = re.split(r'\s[A-E]\)', pregunta)[0]
        # Filtrar basura (muy corta)
        if len(pregunta) > 10:
            preguntas_limpias.append(pregunta)
    
    return preguntas_limpias

def generate_exam_batch(preguntas_lote, num_preguntas_lote, difficulty, tema_general=""):
    """Generar un lote pequeño de preguntas usando IA"""
    
    prompt = f"""
Basándote en las siguientes preguntas de referencia, genera EXACTAMENTE {num_preguntas_lote} preguntas nuevas y diferentes sobre los mismos temas.

Tema general: {tema_general}

Preguntas de referencia:
{json.dumps([{"num": i+1, "texto": p} for i, p in enumerate(preguntas_lote)], ensure_ascii=False)}

Reglas:
- Genera EXACTAMENTE {num_preguntas_lote} preguntas nuevas (no copies las originales)
- Dificultad: {difficulty}
- Cada pregunta debe tener 4 opciones (A-D)
- Marca la respuesta correcta con la letra
- Devuelve SOLO JSON, sin texto adicional
- Formato estricto:
{{
    "preguntas": [
        {{
            "numero": 1,
            "tema": "Tema detectado",
            "pregunta": "Texto de la pregunta",
            "opciones": {{
                "A": "...",
                "B": "...",
                "C": "...",
                "D": "..."
            }},
            "respuesta_correcta": "A"
        }}
    ]
}}
"""

    try:
        chat = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[{"role": "user", "content": prompt}]
        )
        
        generated_text = chat.choices[0].message.content
        
        # Limpiar respuesta para obtener solo JSON
        json_start = generated_text.find('{')
        json_end = generated_text.rfind('}') + 1
        
        if json_start != -1 and json_end != -1:
            json_text = generated_text[json_start:json_end]
            exam_data = json.loads(json_text)
            return exam_data.get("preguntas", [])
        else:
            print("⚠ No se pudo extraer JSON válido de la respuesta de IA")
            return create_fallback_questions(preguntas_lote, num_preguntas_lote)
            
    except Exception as e:
        print(f"❌ Error generando lote con IA: {e}")
        return create_fallback_questions(preguntas_lote, num_preguntas_lote)

def create_fallback_questions(preguntas_lote, num_preguntas):
    """Crear preguntas básicas en caso de fallo de IA"""
    import random
    
    fallback_questions = []
    for i in range(num_preguntas):
        # Usar pregunta de referencia si existe, sino crear genérica
        if i < len(preguntas_lote):
            pregunta_ref = preguntas_lote[i]
        else:
            pregunta_ref = "Pregunta de ejemplo basada en el material"
            
        fallback_questions.append({
            "numero": i + 1,
            "tema": "General",
            "pregunta": pregunta_ref if i < len(preguntas_lote) else pregunta_ref,
            "opciones": {
                "A": "Opción A",
                "B": "Opción B", 
                "C": "Opción C",
                "D": "Opción D"
            },
            "respuesta_correcta": random.choice(["A", "B", "C", "D"])
        })
    
    return fallback_questions

def detectar_tema_general(preguntas_muestra):
    """Detectar el tema general del examen analizando una muestra"""
    try:
        muestra_texto = " ".join(preguntas_muestra[:5])  # Usar solo las primeras 5
        
        prompt = f"""
Analiza estas preguntas y determina el tema o materia principal en 2-3 palabras:

{muestra_texto}

Responde solo con el tema principal (ej: "Matemáticas", "Historia de México", "Biología", etc.)
"""
        
        chat = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return chat.choices[0].message.content.strip()
        
    except:
        return "Materia General"

def generate_exam(pdf_path, num_questions=20, difficulty='medium'):
    """Generar examen usando IA con procesamiento por lotes"""
    print(f"🔄 Generando examen de {num_questions} preguntas...")
    
    # Extraer texto del PDF
    pdf_text = extract_text_from_pdf(pdf_path)
    
    # Extraer preguntas originales
    preguntas_originales = extraer_preguntas(pdf_text)
    print(f"📄 Extraídas {len(preguntas_originales)} preguntas del PDF")
    
    if len(preguntas_originales) == 0:
        print("❌ No se encontraron preguntas en el PDF")
        return {"preguntas": []}
    
    # Detectar tema general
    tema_general = detectar_tema_general(preguntas_originales)
    print(f"📚 Tema detectado: {tema_general}")
    
    # Configurar procesamiento por lotes
    TAMAÑO_LOTE = 2  # Procesar de 2 en 2 como solicitas
    preguntas_por_lote = 2  # Generar 2 preguntas por cada lote
    
    # Calcular número de lotes necesarios
    num_lotes = math.ceil(num_questions / preguntas_por_lote)
    print(f"🔢 Procesando en {num_lotes} lotes de {preguntas_por_lote} preguntas cada uno")
    
    todas_las_preguntas = []
    preguntas_generadas = 0
    
    for i in range(num_lotes):
        print(f"⚡ Procesando lote {i+1}/{num_lotes}...")
        
        # Determinar cuántas preguntas generar en este lote
        preguntas_restantes = num_questions - preguntas_generadas
        preguntas_este_lote = min(preguntas_por_lote, preguntas_restantes)
        
        # Seleccionar preguntas de referencia para este lote (rotar circularmente)
        inicio_ref = (i * TAMAÑO_LOTE) % len(preguntas_originales)
        fin_ref = min(inicio_ref + TAMAÑO_LOTE, len(preguntas_originales))
        
        preguntas_referencia = preguntas_originales[inicio_ref:fin_ref]
        
        # Si no hay suficientes, completar desde el inicio
        while len(preguntas_referencia) < TAMAÑO_LOTE and len(preguntas_originales) > 0:
            preguntas_referencia.extend(preguntas_originales[:TAMAÑO_LOTE - len(preguntas_referencia)])
        
        # Generar preguntas para este lote
        preguntas_lote = generate_exam_batch(
            preguntas_referencia, 
            preguntas_este_lote, 
            difficulty, 
            tema_general
        )
        
        # Renumerar preguntas
        for j, pregunta in enumerate(preguntas_lote):
            pregunta["numero"] = preguntas_generadas + j + 1
        
        todas_las_preguntas.extend(preguntas_lote)
        preguntas_generadas += len(preguntas_lote)
        
        print(f"✅ Lote {i+1} completado: {len(preguntas_lote)} preguntas generadas")
        
        # Si ya tenemos suficientes preguntas, salir
        if preguntas_generadas >= num_questions:
            break
    
    # Truncar si generamos más de las solicitadas
    todas_las_preguntas = todas_las_preguntas[:num_questions]
    
    print(f"🎉 Examen completado: {len(todas_las_preguntas)} preguntas generadas")
    
    return {"preguntas": todas_las_preguntas}

def create_fallback_exam(preguntas_originales, num_questions):
    """Crear examen básico en caso de fallo completo de IA"""
    import random
    
    selected_questions = random.sample(
        preguntas_originales, 
        min(num_questions, len(preguntas_originales))
    )
    
    exam_questions = []
    for i, q in enumerate(selected_questions):
        exam_questions.append({
            "numero": i + 1,
            "tema": "General",
            "pregunta": q,
            "opciones": {
                "A": "Opción A",
                "B": "Opción B",
                "C": "Opción C", 
                "D": "Opción D"
            },
            "respuesta_correcta": "A"
        })
    
    return {"preguntas": exam_questions}
