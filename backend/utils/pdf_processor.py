import os
import fitz
import re
import json
from dotenv import load_dotenv
from openai import OpenAI
import random

# Variables de entorno
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")
if not api_key or not base_url:
    raise ValueError("⚠ Faltan OPENAI_API_KEY o OPENAI_BASE_URL en .env")

client = OpenAI(api_key=api_key, base_url=base_url)

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    pdf_text = ""
    for page in doc:
        pdf_text += page.get_text()
    doc.close()
    return pdf_text

def extraer_preguntas(texto_completo):
    patron = r'(\d+\.\s.*?)(?=\n\d+\.|\Z)'
    bloques = re.findall(patron, texto_completo, re.DOTALL)
    preguntas_limpias = []
    for b in bloques:
        pregunta = " ".join(b.split())
        pregunta = re.split(r'\s[A-E]\)', pregunta)[0]
        if len(pregunta) > 10:
            preguntas_limpias.append(pregunta)
    return preguntas_limpias

def create_fallback_exam(preguntas_originales, num_questions):
    selected_questions = random.sample(preguntas_originales, min(num_questions, len(preguntas_originales)))
    exam_questions = []
    for i, q in enumerate(selected_questions):
        exam_questions.append({
            "numero": i + 1,
            "tema": "General",
            "pregunta": q["texto"],
            "opciones": {"A": "Opción A", "B": "Opción B", "C": "Opción C", "D": "Opción D"},
            "respuesta_correcta": "A"
        })
    return {"preguntas": exam_questions}

def generate_exam(pdf_path, num_questions=20, difficulty='medium'):
    pdf_text = extract_text_from_pdf(pdf_path)
    preguntas_disponibles = extraer_preguntas(pdf_text)
    if not preguntas_disponibles:
        return {"preguntas": []}

    num_questions = min(num_questions, len(preguntas_disponibles))
    exam_questions = []

    for i in range(num_questions):
        pregunta_original = preguntas_disponibles[i]
        # Recortar pregunta a 250 caracteres para reducir uso de memoria
        pregunta_recortada = pregunta_original[:250]

        prompt = f"""
        Genera 1 pregunta de examen a partir de esta pregunta base,
        manteniendo el mismo tema y dificultad {difficulty}.
        Reglas:
        - 4 opciones (A-D)
        - Marca la respuesta correcta
        - Devuelve SOLO JSON, sin texto adicional
        Formato:
        {{
          "preguntas": [
            {{
              "numero": 1,
              "tema": "Tema detectado",
              "pregunta": "Texto de la pregunta",
              "opciones": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
              "respuesta_correcta": "A"
            }}
          ]
        }}
        Pregunta base: {json.dumps({"num": i+1, "texto": pregunta_recortada}, ensure_ascii=False)}
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
                for q in batch_exam["preguntas"]:
                    q["numero"] = len(exam_questions) + 1
                    exam_questions.append(q)
        except Exception as e:
            print(f"Error generando pregunta {i+1}: {e}")
            fallback = create_fallback_exam([{"num": i+1, "texto": pregunta_recortada}], 1)
            for q in fallback["preguntas"]:
                q["numero"] = len(exam_questions) + 1
                exam_questions.append(q)

    return {"preguntas": exam_questions}

