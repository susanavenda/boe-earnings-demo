# BoE earnings demo — PRA Earnings Desk

**Role in the system:** output surface of the Group 9 **automation pipeline**  
(Pipeline notebook/scripts build the pack → this app presents it).

## Run

```bash
cd /Users/susanavenda/Downloads/boe-earnings-demo
source .venv/bin/activate
streamlit run app.py
# → http://localhost:8501
```

## A2 walkthrough (90s)

1. **Episodes** — HSBC H1 opens first (**WATCH**)
2. **Evidence** — struct vs Q&A + quotes
3. **Peer & protocol** — why not peer ALERT
4. **PRA note** — download pack

Pitch script: sibling `Boe_Earnings_Insights_Workspace/docs/assignment2/A2_pitch_outline.md`

## Offline pack

- Live DB: `data/desk.sqlite`
- Frozen copy: `data/snapshots/latest/desk.sqlite`
- Sidebar **Refresh pack from factory** copies Pipeline `boe.sqlite` → `desk.sqlite`
- Ops → Rebuild episodes + PRA only if Stage 8/9 output is missing
