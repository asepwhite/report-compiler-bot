"""Model-based intent classification guardrail for the report bot."""

import logging
from typing import Literal

from pydantic import BaseModel, Field

from app.llm import create_llm


logger = logging.getLogger(__name__)

# Minimum confidence required to block an off-topic request.
_OFF_TOPIC_THRESHOLD = 0.6


class IntentClassification(BaseModel):
    """Structured output from the intent classifier LLM."""

    intent: Literal["report_request", "project_crud", "greeting", "off_topic"] = Field(
        description="Klasifikasi intent dari pesan pengguna."
    )
    confidence: float = Field(
        description="Tingkat kepercayaan klasifikasi, antara 0.0 dan 1.0.",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(
        description="Penjelasan singkat mengapa intent ini dipilih."
    )


_INTENT_CLASSIFIER_PROMPT = """Kamu adalah klasifikasi intent untuk bot pembuat laporan Discord.
Tugasmu mengklasifikasikan pesan pengguna ke dalam salah satu kategori berikut:

1. report_request — Seluruh pesan hanya meminta pembuatan laporan PDF. Basa-basi/sapaan di depan atau belakang diperbolehkan.
   Contoh: "om tolong bikin laporan 10 juni", "report tower 495 dong", "pdf minggu ini ya",
   "tolong buatin laporan untuk kemarin", "laporan bulan lalu", "halo, bisa bantu bikin laporan?".

2. project_crud — Pesan meminta operasi database project: simpan, cari, update, hapus, atau list data project/tower.
   Contoh: "simpan tower T123 di jalur jakarta", "cari project tower T123", "list semua project",
   "update tower T123 roadway jadi Surabaya", "hapus data tower T123 jalur jakarta",
   "tampilkan detail tower T123", "ada berapa tower di region Jawa Barat".

3. greeting — Hanya menyapa, berterima kasih, atau small talk ringan. Tidak ada permintaan laporan atau project CRUD sama sekali.
   Contoh: "halo", "selamat pagi", "hi", "terima kasih", "sama-sama",
   "apa kabar", "good morning".

4. off_topic — Pesan mengandung permintaan atau pertanyaan yang tidak berhubungan dengan pembuatan laporan ATAU project CRUD, TERMASUK jika diselipkan bersama permintaan lain.
   Contoh murni off-topic: "apa itu Python", "bantu kerjain PR matematika", "cuaca hari ini",
   "resep nasi goreng", "berapa harga bitcoin", "cara install Windows".
   Contoh MIXED (laporan/project + off-topic) → off_topic:
   - "bikin laporan tower 495, tapi jarak jakarta ke bandung berapa?"
   - "om tolong bantu bikin laporan @reporting-bot , tapi gw harus tau dulu jarak dari jakarta ke bandung"
   - "report minggu ini dan juga cara install python"
   - "bikin laporan 10 juni, terus besok kita meeting jam berapa?"
   - "simpan tower T123, tapi besok kita meeting jam berapa?"

Peraturan penting:
- Jika pengguna meminta laporan TAPI juga mengajukan pertanyaan atau permintaan lain yang tidak berhubungan dengan laporan/project (misalnya: jarak antar kota, cuaca, bantuan PR, resep, meeting, install software), klasifikasikan sebagai **off_topic**.
- Hanya klasifikasikan sebagai **report_request** jika seluruh pesan hanya berisi permintaan laporan — basa-basi/sapaan diperbolehkan.
- Hanya klasifikasikan sebagai **project_crud** jika seluruh pesan hanya berisi permintaan CRUD project — basa-basi/sapaan diperbolehkan.
- Jika tidak yakin atau ambigu, pilih report_request untuk menghindari false positive.
- Jawab dalam Bahasa Indonesia.

Pesan pengguna: {query}
"""


def classify_intent(user_query: str) -> IntentClassification:
    """
    Classify a user query into report_request, project_crud, greeting, or off_topic.

    Parameters
    ----------
    user_query : str
        The user's message text.

    Returns
    -------
    IntentClassification
        The classified intent. If the LLM classifies as off_topic with
        confidence below the threshold, it is overridden to report_request
        to avoid false positives.
    """
    try:
        llm = create_llm()
        structured_llm = llm.with_structured_output(IntentClassification)

        prompt = _INTENT_CLASSIFIER_PROMPT.format(query=user_query)
        result = structured_llm.invoke(prompt)

        logger.info(
            "Intent classification: intent=%s confidence=%.2f reasoning=%s",
            result.intent,
            result.confidence,
            result.reasoning,
        )

        # If off-topic confidence is below threshold, treat as report request
        # to avoid accidentally blocking legitimate requests.
        if result.intent == "off_topic" and result.confidence < _OFF_TOPIC_THRESHOLD:
            logger.info(
                "Low-confidence off-topic (%.2f < %.2f) overridden to report_request",
                result.confidence,
                _OFF_TOPIC_THRESHOLD,
            )
            return IntentClassification(
                intent="report_request",
                confidence=result.confidence,
                reasoning=f"Dianggap report_request karena confidence off_topic ({result.confidence:.2f}) di bawah threshold ({_OFF_TOPIC_THRESHOLD}). Alasan asli: {result.reasoning}",
            )

        return result

    except Exception:
        logger.exception("Intent classification failed, falling back to report_request")
        return IntentClassification(
            intent="report_request",
            confidence=1.0,
            reasoning="Fallback karena klasifikasi intent gagal. Aman untuk diproses sebagai permintaan laporan.",
        )
