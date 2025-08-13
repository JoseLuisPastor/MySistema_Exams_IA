import os
import fitz  # PyMuPDF
import re
import json
from dotenv import load_dotenv
from openai import OpenAI
import math

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
    """Extraer preguntas sin incisos"""
    patron = r'(\d+\.\s.*?)(?=\n\d+\.|\Z)'
    bloques = re.findall(patron, texto_completo, re.DOTALL)
    preguntas_limpias = []
    for b in bloques:
        pregunta = " ".join(b.split())
        pregunta = re.split(r'\s[A-E]\)', pregunta)[0]
        if len(pregunta) > 10:
            preguntas_limpias.append(pregunta)
    return preguntas_limpias

def generate_exam(pdf_path, num_questions=20, difficulty='medium', batch_size=2):
    """
    Generar examen usando IA en lotes pequeños para evitar saturar memoria.
    batch_size = cuántas preguntas enviamos a la IA en cada request
    """
    # Extraer texto del PDF
    pdf_text = extract_text_from_pdf(pdf_path)
    solo_preguntas = extraer_preguntas(pdf_text)
    preguntas_json = [{"num": i+1, "texto": p} for i, p in enumerate(solo_preguntas)]
    
    # Ajustar número de preguntas si es necesario
    num_questions = min(num_questions, len(preguntas_json))
    
    # Dividir en lotes de tamaño batch_size
    exam_questions = []
    for i in range(0, num_questions, batch_size):
        lote = preguntas_json[i:i+batch_size]
        prompt = f"""
        Analiza las siguientes preguntas y detecta los temas principales. 
        Genera {len(lote)} preguntas de dificultad {difficulty}, manteniendo la proporción de temas.
        Reglas:
        - Las preguntas deben ser completamente diferentes pero sobre los mismos temas.
        - Cada pregunta debe tener 4 opciones (A-D).
        - Marca la respuesta correcta con la letra.
        - Devuelve SOLO JSON, sin texto adicional.
        - Formato estricto:
        {{ "preguntas": [ {{ "numero": 1, "tema": "Tema detectado", "pregunta": "Texto de la pregunta", "opciones": {{ "A": "...", "B": "...", "C": "...", "D": "..." }}, "respuesta_correcta": "A" }} ] }}
        Aquí está el material original: {json.dumps(lote, ensure_ascii=False)}
        """
        try:
            chat = client.chat.completions.create(
                model="deepseek/deepseek-r1:free",
                messages=[{"role": "user", "content": prompt}]
            )
            generated_text = chat.choices[0].message.content
            json_start = generated_text.find('{')
            json_end = generated_text.rfind('}') + 1
            if json_start != -1 and json_end != -1:
                json_text = generated_text[json_start:json_end]
                batch_exam = json.loads(json_text)
                # Ajustar numeración global
                for q in batch_exam["preguntas"]:
                    q["numero"] = len(exam_questions) + 1
                    exam_questions.append(q)
        except Exception as e:
            print(f"Error generando lote de examen con IA: {e}")
            # fallback por lote
            fallback = create_fallback_exam(lote, len(lote))
            for q in fallback["preguntas"]:
                q["numero"] = len(exam_questions) + 1
                exam_questions.append(q)
    
    return {"preguntas": exam_questions}

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
