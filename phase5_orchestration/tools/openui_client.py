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
    "Lethal": {"bg": "#fff5f5", "accent": "#e5484d", "label": "LETHAL - CLASS I"},
    "Moderate": {"bg": "#fffaf0", "accent": "#d97706", "label": "MODERATE - CLASS II"},
    "Minor": {"bg": "#eff6ff", "accent": "#2563eb", "label": "MINOR - CLASS III"},
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
  <h2 style="margin:12px 0 4px;font-size:20px;color:#0f1a2e">{ctx['recalling_firm']}</h2>
  <div style="color:#64748b;font-size:13px;margin-bottom:12px">
  Recall {ctx['recall_number']} &middot; NDC {ctx['product_ndc']}</div>
  <p style="margin:0 0 14px;line-height:1.5;font-size:14px;color:#334155">{ctx['reason_for_recall']}</p>
  <div style="display:flex;gap:18px;border-top:1px solid rgba(20,40,80,.1);padding-top:12px">
    <div><div style="font-size:24px;font-weight:800;color:{theme['accent']}">
    {ctx['customers']:,}</div><div style="color:#64748b;font-size:12px">customers alerted</div></div>
    <div><div style="font-size:24px;font-weight:800;color:#0f1a2e">{ctx['pharmacies']:,}</div>
    <div style="color:#64748b;font-size:12px">pharmacies</div></div>
    <div><div style="font-size:24px;font-weight:800;color:#0f1a2e">{ctx['states']}</div>
    <div style="color:#64748b;font-size:12px">states</div></div>
  </div>
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
        prompt = (
            "Generate a single self-contained HTML snippet (inline styles ONLY, no "
            "<html>/<body>/<script>, no markdown fences) for an emergency drug-recall "
            "alert card embedded in a clean LIGHT-THEME dashboard.\n"
            "Design rules:\n"
            f"- Light card background around {theme['bg']}; dark text (#1a2436).\n"
            f"- Use accent color {theme['accent']} for the severity badge + key numbers.\n"
            f"- Top badge: filled {theme['accent']} background, white text, reading '{theme['label']}'.\n"
            "- Show recalling firm prominently, the recall number + NDC, the reason, "
            "and a stat row with customers alerted / pharmacies / states.\n"
            "- Rounded corners (14px), modern sans-serif, subtle border in the accent, soft shadow.\n"
            "- Make visual urgency scale with severity.\n"
            f"Data: {ctx}\n"
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
