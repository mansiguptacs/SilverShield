"""OpenUI-style runtime card generation.

Calls an LLM (OpenAI) at runtime to generate a self-contained HTML alert card
tailored to the recall's severity. Falls back to a deterministic styled template
when no API key is configured, so the demo always renders.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))
from settings import OPENAI_API_KEY, OPENAI_MODEL  # noqa: E402

SEVERITY_THEME = {
    "Lethal": {"bg": "#fff5f5", "accent": "#e5484d", "label": "LETHAL RECALL - CLASS I",
               "action": "Stop using this medication immediately and seek medical advice. Contact your pharmacy now."},
    "Moderate": {"bg": "#fffaf0", "accent": "#d97706", "label": "MODERATE RECALL - CLASS II",
                 "action": "Stop taking this medication and contact your pharmacy for guidance before your next dose."},
    "Minor": {"bg": "#eff6ff", "accent": "#2563eb", "label": "MINOR RECALL - CLASS III",
              "action": "Please check with your pharmacy before taking your next dose of this medication."},
}


def _fallback_card(ctx: dict) -> str:
    theme = SEVERITY_THEME.get(ctx["severity"], SEVERITY_THEME["Minor"])
    return f"""
<div style="font-family:Inter,system-ui,sans-serif;background:{theme['bg']};
border:1px solid {theme['accent']};border-radius:14px;padding:20px;color:#1a2436;
box-shadow:0 4px 16px rgba(20,40,80,.08)">
  <div style="display:inline-block;background:{theme['accent']};color:#fff;
  font-weight:700;font-size:11px;letter-spacing:.08em;padding:4px 10px;border-radius:6px">
  {theme['label']}</div>
  <h2 style="margin:12px 0 4px;font-size:19px;color:#0f1a2e">Your medication has been recalled</h2>
  <p style="margin:0 0 12px;line-height:1.5;font-size:14px;color:#334155">
  A medication you filled - <b>{ctx['recalling_firm']}</b> (NDC {ctx['product_ndc']}) - has been recalled by the U.S. FDA.</p>
  <div style="background:rgba(255,255,255,.6);border:1px solid rgba(20,40,80,.08);border-radius:10px;padding:11px 13px;margin-bottom:14px">
  <div style="font-size:12px;color:#64748b;margin-bottom:3px">Reason for recall</div>
  <div style="font-size:13px;line-height:1.45;color:#334155">{ctx['reason_for_recall']}</div></div>
  <div style="background:{theme['accent']};color:#fff;border-radius:10px;padding:12px 14px">
  <div style="font-size:11px;letter-spacing:.06em;opacity:.85;margin-bottom:3px">WHAT YOU SHOULD DO</div>
  <div style="font-size:14px;font-weight:600;line-height:1.4">{theme['action']}</div></div>
  <div style="color:#94a3b8;font-size:11px;margin-top:12px">
  Recall {ctx['recall_number']} &middot; Source: U.S. FDA openFDA</div>
</div>""".strip()


def render_alert_card(ctx: dict) -> dict:
    """Return {html, generated_by}. ctx keys: recall_number, severity, product_ndc,
    recalling_firm, reason_for_recall, customers, pharmacies, states."""
    if not OPENAI_API_KEY:
        return {"html": _fallback_card(ctx), "generated_by": "template_fallback"}

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        theme = SEVERITY_THEME.get(ctx["severity"], SEVERITY_THEME["Minor"])
        card_ctx = {
            "recalling_firm": ctx["recalling_firm"], "product_ndc": ctx["product_ndc"],
            "reason_for_recall": ctx["reason_for_recall"], "recall_number": ctx["recall_number"],
            "severity": ctx["severity"],
        }
        prompt = (
            "Generate a single self-contained HTML snippet (inline styles ONLY, no "
            "<html>/<body>/<script>, no markdown fences) for a PATIENT-FACING drug-recall "
            "alert - this is the notification a PATIENT receives, not an admin dashboard.\n"
            "Design rules:\n"
            f"- Light card background around {theme['bg']}; dark text (#1a2436).\n"
            f"- Top badge: filled {theme['accent']} background, white text, reading '{theme['label']}'.\n"
            "- A reassuring but clear headline like 'Your medication has been recalled'.\n"
            "- One plain-language sentence naming the firm + NDC and that the FDA recalled it.\n"
            "- Show the reason for recall in a subtle sub-box.\n"
            f"- A prominent action box (filled {theme['accent']}, white text) titled 'WHAT YOU SHOULD DO' "
            f"with this guidance: \"{theme['action']}\".\n"
            "- Do NOT include internal metrics like customer counts, pharmacy counts, or states.\n"
            "- Small footer: 'Recall <number> - Source: U.S. FDA'.\n"
            "- Rounded corners (14px), modern sans-serif, subtle accent border, soft shadow.\n"
            f"Data: {card_ctx}\n"
            "Return ONLY the HTML for the single card <div>."
        )
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a UI generator that returns only raw HTML with inline styles, designed for a clean light theme."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=900,
        )
        html = resp.choices[0].message.content.strip()
        if html.startswith("```"):
            html = html.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
        return {"html": html, "generated_by": f"openui:{OPENAI_MODEL}"}
    except Exception as exc:  # noqa: BLE001
        return {"html": _fallback_card(ctx), "generated_by": f"fallback ({exc})"}
