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

def llamar_ia_para_lote(pregunta_lote, difficulty):
    """Generar nueva pregunta usando IA a partir de una sola pregunta"""
    prompt = f"""
Analiza la siguiente pregunta y genera una NUEVA pregunta diferente pero del mismo tema,
con dificultad {difficulty}.

Reglas:
- 4 opciones (A-D).
- Indica la respuesta correcta.
- Devuelve SOLO JSON en este formato:
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

Pregunta de referencia:
{json.dumps(pregunta_lote, ensure_ascii=False)}
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
        print(f"⚠ Error IA en pregunta: {e}")
    return {"preguntas": []}

def generate_exam(pdf_path, num_questions=20, difficulty='medium'):
    """Generar examen procesando 1 pregunta por vez"""
    pdf_text = extract_text_from_pdf(pdf_path)
    solo_preguntas = extraer_preguntas(pdf_text)

    preguntas_json = [{"num": i+1, "texto": p} for i, p in enumerate(solo_preguntas)]
    num_questions = min(num_questions, len(preguntas_json))

    examen_final = {"preguntas": []}
    numero_global = 1

    # Procesar de 1 en 1
    for i in range(num_questions):
        lote_pregunta = [preguntas_json[i]]
        resultado_lote = llamar_ia_para_lote(lote_pregunta, difficulty)

        for pregunta in resultado_lote.get("preguntas", []):
            pregunta["numero"] = numero_global
            numero_global += 1
            examen_final["preguntas"].append(pregunta)

    return examen_final
