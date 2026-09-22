"""PRA Earnings Desk — supervisor-first episode readout.

Clean chrome + full evidence on one scroll (nothing hidden behind tabs).
Ops stays buried in the sidebar.
"""
from __future__ import annotations

import html
import json
from datetime import datetime

import pandas as pd
import streamlit as st

from pipeline.auto import ensure_desk
from pipeline.db import list_episodes, read_asset, read_document, read_table
from pipeline.paths import DB_PATH, DEMO_DATA, HAND_LABELS, PIPELINE_ROOT
from pipeline.recalibrate import check_recalibration
from pipeline.registry import load_registry

st.set_page_config(
    page_title="PRA Earnings Desk",
    page_icon="▣",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Serif:wght@600&display=swap');

html, body, [class*="css"] { font-family: "IBM Plex Sans", system-ui, sans-serif; }
.block-container { padding-top: 0.9rem; padding-bottom: 2.5rem; max-width: 1160px; }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }

.topbar {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 1rem; padding: 0.25rem 0 0.8rem;
  border-bottom: 1px solid #d9e2ec; margin-bottom: 1rem;
}
.topbar .brand {
  font-family: "IBM Plex Serif", Georgia, serif;
  font-size: 1.35rem; font-weight: 600; color: #0b1f33; letter-spacing: -0.02em;
  margin: 0;
}
.topbar .meta { font-size: 0.8rem; color: #627d98; text-align: right; }

.verdict-pill {
  display: inline-block; padding: 0.22rem 0.65rem; border-radius: 2px;
  font-weight: 700; font-size: 0.78rem; letter-spacing: 0.06em;
}
.verdict-ALERT { background: #f3d0c7; color: #7a1f12; }
.verdict-WATCH { background: #f5e6c8; color: #6b4e12; }
.verdict-NULL  { background: #d5e5d8; color: #1e4d2b; }
.verdict-OTHER { background: #d9e2ec; color: #243b53; }

.ep-card {
  border: 1px solid #d9e2ec; border-radius: 3px; padding: 0.75rem 0.9rem;
  background: #fff; margin-bottom: 0.45rem;
}
.ep-card.active { border-color: #1a3d5c; box-shadow: inset 3px 0 0 #c4a35a; }
.ep-card .bank {
  font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em; color: #627d98;
}
.ep-card .name { font-weight: 600; color: #102a43; margin: 0.15rem 0 0.35rem; }
.ep-card .sub { font-size: 0.78rem; color: #486581; margin-top: 0.3rem; }

.summary { margin: 0.15rem 0 0.35rem; }
.summary .kicker {
  font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em;
  color: #627d98; font-weight: 600; margin-bottom: 0.35rem;
}
.summary .headline {
  font-family: "IBM Plex Serif", Georgia, serif;
  font-size: 1.28rem; font-weight: 600; color: #0b1f33;
  line-height: 1.35; margin: 0.4rem 0 0.5rem;
}
.summary .why {
  font-size: 0.95rem; color: #243b53; line-height: 1.5; margin: 0 0 0.7rem;
}
.metrics {
  display: flex; flex-wrap: wrap; gap: 1.1rem 1.6rem;
  padding: 0.7rem 0; border-top: 1px solid #e8eef4; border-bottom: 1px solid #e8eef4;
  margin-bottom: 0.35rem;
}
.metrics .m .lbl {
  font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; color: #627d98;
}
.metrics .m .val { font-size: 1.05rem; font-weight: 600; color: #102a43; margin-top: 0.08rem; }

.caveat {
  background: #fff8eb; border-left: 3px solid #c4a35a; color: #5c4813;
  padding: 0.55rem 0.85rem; font-size: 0.88rem; margin: 0.75rem 0 0.25rem;
}

.section-h {
  font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em;
  color: #627d98; font-weight: 600; margin: 1.25rem 0 0.5rem;
  border-bottom: 1px solid #e8eef4; padding-bottom: 0.28rem;
}

.quote-block {
  border-left: 3px solid #1a3d5c; background: #f7f9fb;
  padding: 0.65rem 0.9rem; margin: 0.4rem 0; font-size: 0.9rem; color: #243b53;
}
.quote-meta { font-size: 0.74rem; color: #627d98; margin-bottom: 0.28rem; }

.admin-badge {
  display: inline-block; padding: 0.2rem 0.55rem; border-radius: 2px;
  font-size: 0.72rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
}
.admin-badge.go { background: #d5e5d8; color: #1e4d2b; }
.admin-badge.wait { background: #f5e6c8; color: #6b4e12; }
.admin-card {
  background: #f7f9fb; border: 1px solid #d9e2ec; border-radius: 3px;
  padding: 0.55rem 0.7rem; margin: 0.35rem 0 0.55rem; font-size: 0.82rem; color: #243b53;
}
.admin-card .k { color: #627d98; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; }
.admin-card .v { font-weight: 600; color: #102a43; margin-top: 0.1rem; }
.gate-row { font-size: 0.78rem; color: #243b53; margin: 0.25rem 0 0.1rem; }
.gate-ok { color: #1e4d2b; }
.gate-no { color: #6b4e12; }
.admin-tip {
  background: #f0f4f8; border-left: 3px solid #486581; padding: 0.45rem 0.65rem;
  font-size: 0.76rem; color: #486581; margin: 0.4rem 0 0.55rem;
}

/* Horizontal tab bar */
div[data-testid="stTabs"] [data-baseweb="tab-list"] {
  gap: 0.15rem; border-bottom: 1px solid #d9e2ec; padding-bottom: 0;
}
div[data-testid="stTabs"] button[data-baseweb="tab"] {
  font-size: 0.88rem; font-weight: 500; padding: 0.45rem 0.85rem;
  color: #486581;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
  color: #0b1f33; font-weight: 600;
}
</style>
""",
    unsafe_allow_html=True,
)


def verdict_class(text: str) -> str:
    t = (text or "").upper()
    if t.startswith("ALERT"):
        return "ALERT"
    if t.startswith("WATCH"):
        return "WATCH"
    if t.startswith("NULL"):
        return "NULL"
    return "OTHER"


def short_verdict(text: str) -> str:
    raw = (text or "—").split("—")[0].split("-")[0].strip().upper()
    return raw if raw in {"ALERT", "WATCH", "NULL"} else (text or "—")[:24]


def agree_row(row: pd.Series) -> str:
    rep = str(row.get("reported_direction") or "").lower()
    nar = str(row.get("narrative_direction") or "").strip().lower()
    hits = row.get("n_qa_hits")
    if pd.isna(hits) or int(hits or 0) == 0 or nar in ("", "nan", "none"):
        return "n/a"
    return "yes" if rep == nar else "no"


def fmt_ts(mtime: float) -> str:
    if not mtime:
        return "—"
    return datetime.fromtimestamp(mtime).strftime("%d %b %Y · %H:%M")


def pick_pra_section(text: str, ep: dict) -> str:
    bank = (ep.get("bank") or "").upper()
    chunks = text.split("\n\n---\n\n")
    for ch in chunks:
        if bank and bank in ch and (ep.get("calendar_period") or "") in ch:
            return ch
        label = ep.get("label") or ""
        if label and label.split()[0].upper() in ch:
            if any(x in ch for x in (ep.get("quarter") or "", ep.get("calendar_period") or "")):
                return ch
    return text


def _esc(v) -> str:
    return html.escape("" if v is None else str(v))


def _gate_bar(have: int, need: int, label: str) -> None:
    need = max(1, int(need))
    have = max(0, int(have))
    pct = min(1.0, have / need)
    ok = have >= need
    mark = "✓" if ok else "·"
    cls = "gate-ok" if ok else "gate-no"
    st.markdown(
        f'<div class="gate-row {cls}">{mark} {label}: <strong>{have}</strong> / {need}</div>',
        unsafe_allow_html=True,
    )
    st.progress(pct)


def request_refresh() -> None:
    """Copy factory boe.sqlite → desk.sqlite on the next rerun."""
    st.session_state.force_refresh = True
    st.rerun()


def render_refresh_button() -> None:
    if st.button(
        "Refresh pack from factory",
        use_container_width=True,
        type="secondary",
        help="Copies Pipeline data/boe.sqlite into this desk. Run the notebook first if PDFs or Excel changed.",
    ):
        request_refresh()
    st.caption(
        "Does not re-run the notebook. Factory work lives in boe.sqlite — "
        "run Stages 1–9, then click this to copy the pack here."
    )


def render_ops_panel(status: dict) -> None:
    if st.button("Rebuild episodes + PRA", use_container_width=True):
        with st.spinner("Rebuilding…"):
            st.session_state.desk_status = ensure_desk(
                force=True, rebuild_episodes=True
            )
            st.cache_data.clear()
        st.rerun()

    st.markdown(
        f"""
        <div class="admin-card">
          <div class="k">Pack updated</div>
          <div class="v">{_esc(fmt_ts(status.get("desk_mtime") or 0))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("##### Recalibration")
    if st.button("Check gates", use_container_width=True):
        st.session_state.show_recal = True
    if st.session_state.get("show_recal"):
        chk = check_recalibration()
        ready = bool(chk.get("retrain_recommended"))
        st.markdown(
            '<span class="admin-badge go">Ready to train</span>'
            if ready
            else '<span class="admin-badge wait">Not yet</span>',
            unsafe_allow_html=True,
        )
        gates = chk.get("gates") or {}
        _gate_bar(chk.get("n_human_labels") or 0, gates.get("min_human_rows") or 40, "Human labels")
        _gate_bar(
            chk.get("n_new_since_promote") or 0,
            gates.get("min_new_since_promote") or 15,
            "New since promote",
        )
        for tip in (chk.get("advice") or [])[:2]:
            st.markdown(f'<div class="admin-tip">{_esc(tip)}</div>', unsafe_allow_html=True)

    reg = load_registry()
    st.markdown(
        f"""
        <div class="admin-card">
          <div class="k">Active model</div>
          <div class="v">{_esc(reg.get("active_model_id") or "Zero-shot FinBERT — none promoted")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# —— Bootstrap ——————————————————————————————————————————————
force = bool(st.session_state.pop("force_refresh", False))
if "desk_status" not in st.session_state or force:
    if force or not DB_PATH.exists():
        with st.spinner("Loading supervisory pack…"):
            st.session_state.desk_status = ensure_desk(force=force)
            st.cache_data.clear()
    else:
        st.session_state.desk_status = ensure_desk(force=False)

status = st.session_state.desk_status


@st.cache_data
def _episodes(mtime: float) -> list[dict]:
    _ = mtime
    return list_episodes()


@st.cache_data
def _table(name: str, episode_id: str | None, mtime: float) -> pd.DataFrame:
    _ = mtime
    return read_table(name, episode_id=episode_id)


mt = status.get("desk_mtime") or (DB_PATH.stat().st_mtime if DB_PATH.exists() else 0)

st.markdown(
    f"""
    <div class="topbar">
      <p class="brand">PRA Earnings Desk</p>
      <div class="meta">Group 9 · pack {_esc(fmt_ts(mt))}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not status.get("desk_ready") and not DB_PATH.exists():
    st.error(
        "No supervisory pack yet. Run the Pipeline notebook once, then click **Refresh pack from factory**."
    )
    with st.sidebar:
        render_refresh_button()
        render_ops_panel(status)
    st.stop()

episodes = _episodes(mt)
if not episodes:
    st.warning("Desk has no episodes yet.")
    with st.sidebar:
        if st.button("Build episodes from Pipeline", use_container_width=True):
            st.session_state.desk_status = ensure_desk(force=True, rebuild_episodes=True)
            st.cache_data.clear()
            st.rerun()
    st.stop()

labels = [e.get("label") or e.get("id") for e in episodes]
by_label = {e.get("label") or e.get("id"): e for e in episodes}


def _default_episode(labs: list[str]) -> str:
    """A2 walkthrough starts on HSBC H1 / interim."""
    for lab in labs:
        low = lab.lower()
        if "hsbc" in low and ("interim" in low or "h1" in low or "2025" in low):
            return lab
    for lab in labs:
        if "hsbc" in lab.lower():
            return lab
    return labs[0]


if "selected_episode" not in st.session_state:
    st.session_state.selected_episode = _default_episode(labels)
if st.session_state.selected_episode not in by_label:
    st.session_state.selected_episode = _default_episode(labels)

with st.sidebar:
    st.markdown("#### Episodes")
    for lab in labels:
        ep0 = by_label[lab]
        sv0 = short_verdict(ep0.get("verdict", ""))
        period = ep0.get("calendar_period") or ep0.get("quarter") or ""
        bank = (ep0.get("bank") or "").upper()
        selected = lab == st.session_state.selected_episode
        if st.button(
            f"{sv0}  ·  {bank} {period}",
            key=f"nav_{lab}",
            use_container_width=True,
            type="primary" if selected else "secondary",
        ):
            st.session_state.selected_episode = lab
            st.rerun()
    st.divider()
    render_refresh_button()
    with st.expander("Ops", expanded=False):
        st.caption("Engineering controls only.")
        render_ops_panel(status)

ep = by_label[st.session_state.selected_episode]
eid = ep.get("id")
vc = verdict_class(ep.get("verdict", ""))
sv = short_verdict(ep.get("verdict", ""))
net = ep.get("finbert_net")
net_s = f"{net:.3f}" if isinstance(net, (int, float)) else "—"
period = _esc(ep.get("calendar_period") or ep.get("quarter") or "")
bank = _esc((ep.get("bank") or "").upper())
neg = ep.get("topic1_neg_share")
neg_s = f"{float(neg):.0%}" if isinstance(neg, (int, float)) else "—"

def load_json_doc(*parts: str) -> dict | None:
    path = PIPELINE_ROOT.joinpath(*parts)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return None
    return None


def load_agreement() -> dict | None:
    return load_json_doc("docs", "assignment2", "label_agreement.json")


def load_m2a() -> dict | None:
    return load_json_doc("docs", "assignment2", "human_labels", "m2a_agreement.json")


# Context strip stays visible while switching tabs
st.markdown(
    f"""
    <div style="display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;margin:0 0 0.35rem">
      <span class="verdict-pill verdict-{vc}">{_esc(sv)}</span>
      <span style="font-weight:600;color:#102a43">{_esc(ep.get("label") or "")}</span>
      <span style="font-size:0.82rem;color:#627d98">{bank} · {period}</span>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(
    "Automation pipeline output · A2 path: Episodes (HSBC H1) → Evidence → Peer & protocol → PRA note. "
    "Factory = Pipeline notebook/scripts · Ops = engineering only."
)

_agr = load_agreement()
if _agr and _agr.get("pitch_line"):
    st.caption(_agr["pitch_line"])
_m2a = load_m2a()
if _m2a and _m2a.get("pitch_line"):
    st.caption(_m2a["pitch_line"])

tab_episodes, tab_evidence, tab_topics, tab_peer, tab_briefs, tab_pra = st.tabs(
    [
        "Episodes",
        "Evidence",
        "Topics",
        "Peer & protocol",
        "Briefs",
        "PRA note",
    ]
)

with tab_episodes:
    st.markdown(
        f"""
        <div class="summary">
          <div class="kicker">{bank} · {period}</div>
          <span class="verdict-pill verdict-{vc}">{_esc(sv)}</span>
          <p class="headline">{_esc(ep.get("headline") or ep.get("label") or "Episode")}</p>
          <p class="why">{_esc(ep.get("verdict") or "")}</p>
          <div class="metrics">
            <div class="m"><div class="lbl">FinBERT net</div><div class="val">{_esc(net_s)}</div></div>
            <div class="m"><div class="lbl">Analyst turns</div><div class="val">{_esc(ep.get("n_turns", "—"))}</div></div>
            <div class="m"><div class="lbl">Topic 1 turns</div><div class="val">{_esc(ep.get("topic1_turns", "—"))}</div></div>
            <div class="m"><div class="lbl">Topic 1 neg</div><div class="val">{_esc(neg_s)}</div></div>
            <div class="m"><div class="lbl">Rules</div><div class="val">{_esc(", ".join(ep.get("rules_fired") or ["—"]))}</div></div>
          </div>
          {f'<div class="caveat"><strong>Peer caveat</strong> — {_esc(ep["peer_caveat"])}</div>' if ep.get("peer_caveat") else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )
    if ep.get("pitch_angle"):
        st.caption(f"Pitch angle — {ep['pitch_angle']}")

with tab_evidence:
    briefs = _table("metric_briefs", eid, mt)
    st.markdown('<div class="section-h">Struct vs Q&A</div>', unsafe_allow_html=True)
    if briefs is not None and not briefs.empty:
        view = briefs.copy()
        view["agree"] = view.apply(agree_row, axis=1)
        cols_b = [
            c
            for c in [
                "metric",
                "reported_direction",
                "narrative_direction",
                "agree",
                "n_qa_hits",
                "qa_finbert_net",
                "claim",
            ]
            if c in view.columns
        ]
        st.dataframe(view[cols_b], use_container_width=True, hide_index=True)
    else:
        st.caption("No metric briefs for this episode.")

    quotes = _table("quotes", eid, mt)
    st.markdown('<div class="section-h">Analyst quotes</div>', unsafe_allow_html=True)
    if quotes is not None and not quotes.empty:
        for _, q in quotes.head(8).iterrows():
            sent = str(q.get("finbert_sentiment", ""))
            text = str(q.get("text", ""))
            st.markdown(
                f"""
                <div class="quote-block">
                  <div class="quote-meta">{_esc(q.get("speaker", ""))} · {_esc(q.get("firm", ""))}
                  · topic {_esc(q.get("topic", ""))} · <strong>{_esc(sent)}</strong>
                  ({float(q.get("finbert_score") or 0):.2f})</div>
                  {_esc(text[:480])}{"…" if len(text) > 480 else ""}
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.caption("No quotes stored.")

    st.markdown('<div class="section-h">Answering behaviour (M6)</div>', unsafe_allow_html=True)
    ss = _table("state_summary", None, mt)
    if ss is not None and not ss.empty:
        view = ss.copy()
        if ep.get("bank") and "bank" in view.columns:
            bank_mask = view["bank"].astype(str).str.lower() == str(ep["bank"]).lower()
            if bank_mask.any():
                view = view[bank_mask]
        cols_s = [
            c
            for c in [
                "bank",
                "quarter",
                "n",
                "mean_directness",
                "metric_coverage_rate",
                "substitution_rate",
                "total_income",
                "operating_costs",
                "credit_impairment",
                "cet1_ratio",
            ]
            if c in view.columns
        ]
        st.dataframe(view[cols_s], use_container_width=True, hide_index=True)
        st.caption("n = Q&A pairs. Substitution is avoidance-as-behaviour, not a FinBERT label.")
    else:
        st.caption("No state_summary in this pack — re-run Pipeline `scripts/build_a1_evidence.py`.")

with tab_topics:
    topics = _table("topic_share", eid, mt)
    st.markdown('<div class="section-h">Topic share</div>', unsafe_allow_html=True)
    if topics is not None and not topics.empty:
        show_t = topics.copy()
        prefer = [
            c
            for c in ["topic", "label", "n_turns", "share", "neg_share", "finbert_net"]
            if c in show_t.columns
        ]
        st.dataframe(
            show_t[prefer] if prefer else show_t,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No topic-share rows for this episode.")

with tab_peer:
    left, right = st.columns(2)
    with left:
        st.markdown('<div class="section-h">Matched peer</div>', unsafe_allow_html=True)
        gap = ep.get("peer_gap_hsbc_minus_barclays")
        hs = ep.get("peer_hsbc_net")
        ba = ep.get("peer_barclays_net")
        hs_s = f"{hs:.3f}" if isinstance(hs, (int, float)) else "—"
        ba_s = f"{ba:.3f}" if isinstance(ba, (int, float)) else "—"
        gap_s = f"{gap:.3f}" if isinstance(gap, (int, float)) else "—"
        st.write(
            f"HSBC {hs_s} (n={ep.get('peer_hsbc_n', '—')}) · "
            f"Barclays {ba_s} (n={ep.get('peer_barclays_n', '—')}) · "
            f"gap {gap_s} · A2-usable {'yes' if ep.get('peer_usable_for_a2') else 'no'}"
        )
        peer_gap = _table("peer_gap", None, mt)
        if peer_gap is not None and not peer_gap.empty:
            st.dataframe(peer_gap, use_container_width=True, hide_index=True)
        peer_file = DEMO_DATA / "peer_gap_matched.png"
        if peer_file.exists():
            st.image(str(peer_file), use_container_width=True)
        else:
            blob = read_asset("peer_gap_matched.png")
            if blob:
                st.image(blob, use_container_width=True)
    with right:
        st.markdown('<div class="section-h">Alert / null protocol</div>', unsafe_allow_html=True)
        proto = _table("protocol", None, mt)
        fired = set(ep.get("rules_fired") or [])
        if proto is not None and not proto.empty:
            show = proto.copy()
            show["status"] = show["rule_id"].map(lambda r: "FIRED" if r in fired else "—")
            st.dataframe(
                show[["rule_id", "severity", "status", "condition"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No protocol table.")

with tab_briefs:
    faith = _table("metric_briefs_faithful", None, mt)
    st.markdown('<div class="section-h">Extractive metric briefs</div>', unsafe_allow_html=True)
    if faith is not None and not faith.empty:
        fview = faith.copy()
        if "bank" in fview.columns and ep.get("bank"):
            fview = fview[
                fview["bank"].astype(str).str.lower() == str(ep["bank"]).lower()
            ]
        cols_f = [
            c
            for c in [
                "bank",
                "quarter",
                "metric",
                "method",
                "faithfulness_overlap",
                "summary",
            ]
            if c in fview.columns
        ]
        st.dataframe(fview[cols_f].head(12), use_container_width=True, hide_index=True)
    else:
        st.caption("No faithful briefs in desk pack.")

    agr = load_agreement()
    st.markdown('<div class="section-h">Label agreement</div>', unsafe_allow_html=True)
    if agr and agr.get("metrics"):
        st.caption(agr.get("pitch_line") or "")
        st.dataframe(pd.DataFrame(agr["metrics"]), use_container_width=True, hide_index=True)
        st.caption(
            f"Hand queue: {agr.get('n_hand_sample')} rows "
            f"({agr.get('n_human_reviewed_flag')} reviewed · "
            f"{agr.get('n_provisional_queue')} provisional) · {HAND_LABELS.name}"
        )
    else:
        st.caption("Run Pipeline `scripts/label_agreement.py` to refresh metrics.")

    m2a = load_m2a()
    st.markdown('<div class="section-h">8-way dual-code</div>', unsafe_allow_html=True)
    if m2a:
        st.caption(m2a.get("pitch_line") or "")
        rows = []
        for key in (
            "machine_coder1_vs_coder2",
            "machine_coder1_vs_aidan_pair",
            "machine_coder2_vs_aidan_pair",
        ):
            block = m2a.get(key) or {}
            if block:
                rows.append(
                    {
                        "comparison": key,
                        "n": block.get("n"),
                        "agree": block.get("n_agree"),
                        "pct": block.get("pct"),
                    }
                )
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("Run Pipeline `scripts/score_m2a_human.py` to refresh 8-way scores.")

with tab_pra:
    st.markdown('<div class="section-h">PRA one-pager</div>', unsafe_allow_html=True)
    pra = read_document("pra_notes.md")
    if pra:
        st.markdown(pick_pra_section(pra, ep))
        st.download_button(
            "Download full PRA pack",
            data=pra,
            file_name="pra_notes.md",
            mime="text/markdown",
            type="primary",
        )
    else:
        st.caption("PRA note missing — use Ops → Rebuild episodes + PRA.")
