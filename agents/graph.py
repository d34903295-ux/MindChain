"""Orquestación LangGraph Fase 0/1: profile -> score -> explain."""
from langgraph.graph import StateGraph, END
from typing import TypedDict
from .wallet_intelligence import profile_wallet
from .risk_scoring import score_wallet
from .explanation import explain

class State(TypedDict, total=False):
    address: str; txs: list; profile: dict; risk_score: int; risk_factors: list; explanation: str

def n_profile(s: State) -> State:
    s["profile"] = profile_wallet(s["address"], s.get("txs", []))
    return s

def n_score(s: State) -> State:
    sc, fac = score_wallet(s["profile"], s.get("txs", []))
    s["risk_score"] = sc; s["risk_factors"] = fac
    return s

def n_explain(s: State) -> State:
    s["explanation"] = explain(s["profile"], s["risk_score"], s["risk_factors"])
    return s

def build_graph():
    g = StateGraph(State)
    g.add_node("profile", n_profile); g.add_node("score", n_score); g.add_node("explain", n_explain)
    g.set_entry_point("profile")
    g.add_edge("profile", "score"); g.add_edge("score", "explain"); g.add_edge("explain", END)
    return g.compile()

graph = build_graph()
