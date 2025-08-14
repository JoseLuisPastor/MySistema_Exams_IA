import os
import fitz  # PyMuPDF
import re
import json
import gc
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
    with fitz.open(pdf_path) as doc:
        return "\n".join([page.get_text() for page in doc])

def extraer_preguntas(texto_completo):
    """Extraer preguntas sin incisos"""
    patron = r'(\d+\.\s.*?)(?=\n\d+\.|\Z)'
    bloques = re.findall(patron, texto_completo, re.DOTALL)
    preguntas_limpias = []
    for b in bloques:
        pregunta = " ".join(b.split())
        pregunta = re.split(r'\s[A-E]\)', pregunta)[0]
        if len(pregunta) > 10:
            # Limitar largo de la pregunta para no saturar tokens
            preguntas_limpias.append(pregunta[:500])
    return preguntas_limpias

def llamar_ia_para_lote(preguntas_lote, difficulty):
    """Generar nuevas preguntas usando IA a partir de un lote"""
    prompt = f"""
Genera {len(preguntas_lote)} nuevas preguntas basadas en las siguientes, manteniendo el mismo tema y dificultad {difficulty}.

Reglas:
- 4 opciones (A-D).
- Indicar la respuesta correcta.
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

Preguntas de referencia:
{json.dumps(preguntas_lote, ensure_ascii=False)}
"""
    try:
        chat = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        generated_text = chat.choices[0].message.content
        json_start = generated_text.find('{')
        json_end = generated_text.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            return json.loads(generated_text[json_start:json_end])
    except Exception as e:
        print(f"⚠ Error IA en lote: {e}")
    return {"preguntas": []}

def generate_exam(pdf_path, num_questions=20, difficulty='medium'):
    """Generar examen procesando en lotes"""
    pdf_text = extract_text_from_pdf(pdf_path)
    solo_preguntas = extraer_preguntas(pdf_text)

    # Limitar a las que pidió el usuario
    solo_preguntas = solo_preguntas[:num_questions]

    examen_final = {"preguntas": []}
    numero_global = 1

    # Procesar en lotes de 3 para menos llamadas a la IA
    lote_tamano = 3
    for i in range(0, len(solo_preguntas), lote_tamano):
        lote_preguntas = [{"num": idx+1, "texto": p} for idx, p in enumerate(solo_preguntas[i:i+lote_tamano])]
        resultado_lote = llamar_ia_para_lote(lote_preguntas, difficulty)

        for pregunta in resultado_lote.get("preguntas", []):
            pregunta["numero"] = numero_global
            numero_global += 1
            examen_final["preguntas"].append(pregunta)

        # Liberar memoria
        del lote_preguntas, resultado_lote
        gc.collect()

    return examen_final
