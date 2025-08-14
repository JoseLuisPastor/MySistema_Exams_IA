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

def llamar_ia_para_lote(preguntas_lote, difficulty):
    """Generar preguntas para un lote usando IA"""
    prompt = f"""
Analiza las siguientes preguntas y genera un examen NUEVO con el mismo tema y dificultad {difficulty}.
- Devuelve SOLO JSON en este formato estricto:
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
Aquí están las preguntas de referencia:
{json.dumps(preguntas_lote, ensure_ascii=False)}
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
            return json.loads(json_text)
    except Exception as e:
        print(f"⚠ Error en lote: {e}")
    return {"preguntas": []}

def generate_exam(pdf_path, num_questions=20, difficulty='medium'):
    """Generar examen dividiendo en lotes para evitar timeout"""
    pdf_text = extract_text_from_pdf(pdf_path)
    solo_preguntas = extraer_preguntas(pdf_text)

    # Convertir a lista de dicts
    preguntas_json = [{"num": i+1, "texto": p} for i, p in enumerate(solo_preguntas)]

    # Ajustar si hay menos preguntas
    num_questions = min(num_questions, len(preguntas_json))

    # Dividir en lotes de 2
    lotes = []
    for i in range(0, num_questions, 2):
        lote_preguntas = preguntas_json[i:i+2]
        lotes.append(lote_preguntas)

    examen_final = {"preguntas": []}
    numero_global = 1

    for lote in lotes:
        resultado_lote = llamar_ia_para_lote(lote, difficulty)
        for pregunta in resultado_lote.get("preguntas", []):
            pregunta["numero"] = numero_global
            numero_global += 1
            examen_final["preguntas"].append(pregunta)

    return examen_final
