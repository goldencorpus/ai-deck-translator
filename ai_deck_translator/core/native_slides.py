"""
Native Google Slides translation.

Translates a Google Slides presentation in place (via the Slides API) instead of
round-tripping through PPTX. It copies the source deck in Drive, extracts text, runs the
hardened translation engine (dedup + verbatim-JSON parsing + retry + completeness gate,
reused from the PPTX path), and writes results back with deleteText/insertText
batchUpdate requests. Google Slides handles layout/autofit natively, so there is no size
cap or formatting round-trip loss.

The original is never modified — a new translated copy is created in the user's Drive.
"""

from ..auth.google_auth import authenticate_google
from ..pptx.translator import describe_block, missing_block_ids, translate_text
from ..utils.exceptions import IncompleteTranslationError, TranslationError
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Separator for table-cell IDs: "<tableObjectId>__r<row>c<col>".
_CELL_SEP = "__r"


def _runs_text(text_obj):
    """Join the textRun content of a Slides text object."""
    return "".join(
        te.get("textRun", {}).get("content", "")
        for te in (text_obj or {}).get("textElements", [])
        if "textRun" in te
    )


def extract_slides_text(slides_service, presentation_id):
    """Return (presentation, {block_id: text}) for shapes and table cells with text."""
    presentation = (
        slides_service.presentations().get(presentationId=presentation_id).execute()
    )
    text_dict = {}
    for slide in presentation.get("slides", []):
        for element in slide.get("pageElements", []):
            object_id = element.get("objectId")
            shape = element.get("shape")
            if shape and "text" in shape:
                text = _runs_text(shape.get("text"))
                if text.strip():
                    text_dict[object_id] = text.strip()
            table = element.get("table")
            if table:
                for r, row in enumerate(table.get("tableRows", [])):
                    for c, cell in enumerate(row.get("tableCells", [])):
                        text = _runs_text(cell.get("text"))
                        if text.strip():
                            text_dict[f"{object_id}{_CELL_SEP}{r}c{c}"] = text.strip()
    return presentation, text_dict


def _build_replace_requests(translated):
    """Build deleteText+insertText batchUpdate requests for each translated block."""
    requests = []
    for block_id, new_text in translated.items():
        if _CELL_SEP in block_id:
            base_id, rc = block_id.split(_CELL_SEP, 1)
            row_str, col_str = rc.split("c", 1)
            location = {"rowIndex": int(row_str), "columnIndex": int(col_str)}
            requests.append(
                {
                    "deleteText": {
                        "objectId": base_id,
                        "cellLocation": location,
                        "textRange": {"type": "ALL"},
                    }
                }
            )
            requests.append(
                {
                    "insertText": {
                        "objectId": base_id,
                        "cellLocation": location,
                        "insertionIndex": 0,
                        "text": new_text,
                    }
                }
            )
        else:
            requests.append(
                {"deleteText": {"objectId": block_id, "textRange": {"type": "ALL"}}}
            )
            requests.append(
                {
                    "insertText": {
                        "objectId": block_id,
                        "insertionIndex": 0,
                        "text": new_text,
                    }
                }
            )
    return requests


def translate_presentation_native(
    presentation_id,
    source_language="auto",
    target_language="ja",
    api_key=None,
    progress_callback=None,
):
    """
    Translate a Google Slides presentation natively and return (new_id, edit_url).

    Copies the source deck, translates the copy in place, and refuses to keep a partial
    result: if any text block is left untranslated after the retry pass, raises
    IncompleteTranslationError (the partial copy is left in Drive for inspection).
    """
    slides_service, drive_service = authenticate_google()

    src = slides_service.presentations().get(presentationId=presentation_id).execute()
    title = src.get("title", "Presentation")
    logger.info(f"Copying '{title}' before translating (original is untouched)")
    copied = (
        drive_service.files()
        .copy(fileId=presentation_id, body={"name": f"{title} ({target_language})"})
        .execute()
    )
    new_id = copied["id"]
    edit_url = f"https://docs.google.com/presentation/d/{new_id}/edit"

    _, text_dict = extract_slides_text(slides_service, new_id)
    logger.info(f"Extracted {len(text_dict)} text blocks")
    if not text_dict:
        raise TranslationError("No translatable text found in the presentation")

    # Reuse the hardened engine (dedup, small batches, verbatim-JSON, retry).
    slide_metadata = []  # objectId keys carry no slide-number context; not needed
    translated = translate_text(
        text_dict,
        slide_metadata,
        source_language,
        target_language,
        api_key=api_key,
        progress_callback=progress_callback,
    )

    # Completeness gate: never leave a half-translated deck silently.
    missing = missing_block_ids(text_dict, translated)
    total = len(text_dict)
    if missing:
        details = [describe_block(b, text_dict.get(b, "")) for b in missing]
        raise IncompleteTranslationError(
            message=(
                f"{len(missing)}/{total} text blocks were not translated.\n"
                + "\n".join(f"  - {d}" for d in details)
            ),
            missing_ids=missing,
            total=total,
        )
    logger.info(f"Completeness check: {total}/{total} blocks translated (100%)")

    requests = _build_replace_requests(translated)
    for i in range(0, len(requests), 400):  # Slides API caps at 500 requests/batch
        slides_service.presentations().batchUpdate(
            presentationId=new_id, body={"requests": requests[i : i + 400]}
        ).execute()

    logger.info(f"Native Slides translation complete: {edit_url}")
    return new_id, edit_url
