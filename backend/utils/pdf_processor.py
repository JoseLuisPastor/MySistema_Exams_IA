import os
import fitz  # PyMuPDF
import re
import json
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

def generate_exam(pdf_path, num_questions=20, difficulty='medium'):
    """Generar examen usando IA"""
    # Extraer texto del PDF
    pdf_text = extract_text_from_pdf(pdf_path)
    
    # Extraer preguntas originales
    solo_preguntas = extraer_preguntas(pdf_text)
    preguntas_json = [{"num": i+1, "texto": p} for i, p in enumerate(solo_preguntas)]
    
    # Ajustar número de preguntas si es necesario
    num_questions = min(num_questions, len(preguntas_json))
    
    # Prompt para la IA
    prompt = f"""
Analiza el siguiente examen y detecta los temas principales.
Luego, genera 1 examen con {num_questions} preguntas de dificultad {difficulty},
manteniendo la proporción de preguntas por tema.

Reglas:
- El examen debe tener preguntas completamente diferentes, pero sobre los mismos temas.
- Cada pregunta debe tener 4 opciones (A-D).
- Marca la respuesta correcta con la letra.
- Devuelve SOLO JSON, sin texto adicional.
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

Aquí está el material original:
{json.dumps(preguntas_json[:50], ensure_ascii=False)}  # Limitar para evitar exceder tokens
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
            return exam_data
        else:
            # Fallback: crear examen básico si falla la IA
            return create_fallback_exam(preguntas_json, num_questions)
            
    except Exception as e:
        print(f"Error generando examen con IA: {e}")
        return create_fallback_exam(preguntas_json, num_questions)

def create_fallback_exam(preguntas_originales, num_questions):
    """Crear examen básico en caso de fallo de IA"""
    import random
    
    selected_questions = random.sample(preguntas_originales, min(num_questions, len(preguntas_originales)))
    
    exam_questions = []
    for i, q in enumerate(selected_questions):
        exam_questions.append({
            "numero": i + 1,
            "tema": "General",
            "pregunta": q["texto"],
            "opciones": {
                "A": "Opción A",
                "B": "Opción B", 
                "C": "Opción C",
                "D": "Opción D"
            },
            "respuesta_correcta": "A"
        })
    
    return {"preguntas": exam_questions}
