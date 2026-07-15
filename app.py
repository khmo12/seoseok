# -*- coding: utf-8 -*-
"""
서석고등학교 교장 시뮬레이션 - Flask 웹서버
- Colab/ipywidgets 대신 순수 웹(HTML/JS + Flask API)으로 재구성한 버전입니다.
- Gemini API 키는 서버 환경변수(GEMINI_API_KEY 또는 GOOGLE_API_KEY)로만 읽으며,
  브라우저(클라이언트)에는 절대 노출되지 않습니다.
"""

import os
import uuid
import random

from flask import Flask, request, jsonify, session, render_template

import game_core as gc

app = Flask(__name__)
# SESSION_SECRET 환경변수가 있으면 그걸 쓰고, 없으면 서버 재시작마다 새로 생성합니다.
app.secret_key = os.environ.get("SESSION_SECRET", os.urandom(24).hex())

# 세션별 게임 상태는 서버 메모리에 보관합니다 (쿠키 용량 제한을 피하기 위함).
# 데모/개인용 소규모 배포에 적합한 방식입니다. 다중 서버(멀티 워커) 환경에서는
# Redis 등 외부 저장소로 교체가 필요합니다.
GAMES: dict[str, dict] = {}


def _get_game():
    """현재 브라우저 세션에 연결된 게임 데이터를 가져오거나 새로 만듭니다."""
    sid = session.get("sid")
    if not sid or sid not in GAMES:
        sid = uuid.uuid4().hex
        session["sid"] = sid
        GAMES[sid] = _new_game()
    return GAMES[sid]


def _new_game():
    return {
        "state": gc.GameState(),
        "principal_name": "OO",
        "used_side_titles": set(),
        "game_log": [],
        "current_event": None,
        "current_is_side": False,
        "game_over": False,
    }


def _state_dict(state: gc.GameState):
    return {
        "budget": state.budget,
        "reputation": state.reputation,
        "satisfaction": state.satisfaction,
        "morale": state.morale,
        "academic": state.academic,
        "month_index": state.month_index,
        "month_label": gc.MONTH_LABELS[min(state.month_index, len(gc.MONTH_LABELS) - 1)],
    }


def _event_dict(event, is_side):
    return {
        "title": event["title"],
        "desc": event["desc"],
        "is_side": is_side,
        "choices": [
            {"index": i, "text": c[0]} for i, c in enumerate(event["choices"])
        ],
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/start", methods=["POST"])
def api_start():
    data = request.get_json(silent=True) or {}
    name = (data.get("principal_name") or "").strip()

    sid = uuid.uuid4().hex
    session["sid"] = sid
    game = _new_game()
    game["principal_name"] = name if name else "OO"
    game["current_event"] = gc.MAIN_EVENTS[0]
    game["current_is_side"] = False
    GAMES[sid] = game

    return jsonify({
        "principal_name": game["principal_name"],
        "state": _state_dict(game["state"]),
        "event": _event_dict(game["current_event"], False),
    })


@app.route("/api/choice", methods=["POST"])
def api_choice():
    game = _get_game()
    if game["game_over"] or game["current_event"] is None:
        return jsonify({"error": "게임이 시작되지 않았거나 이미 종료되었습니다."}), 400

    data = request.get_json(silent=True) or {}
    idx = data.get("choice_index")
    event = game["current_event"]
    if not isinstance(idx, int) or idx < 0 or idx >= len(event["choices"]):
        return jsonify({"error": "잘못된 선택지입니다."}), 400

    choice_text, effects, result_text = event["choices"][idx]
    return _apply_and_respond(game, effects, result_text, choice_text)


@app.route("/api/custom", methods=["POST"])
def api_custom():
    game = _get_game()
    if game["game_over"] or game["current_event"] is None:
        return jsonify({"error": "게임이 시작되지 않았거나 이미 종료되었습니다."}), 400

    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "문장을 입력해주세요."}), 400

    event = game["current_event"]
    effects, result_text, source = gc.evaluate_custom_action(
        text, event["title"], event["desc"], game["state"]
    )
    tagged_result = f"[{source}] {result_text}"
    return _apply_and_respond(game, effects, tagged_result, text)


def _apply_and_respond(game, effects, result_text, choice_text):
    event = game["current_event"]
    is_side = game["current_is_side"]

    if is_side:
        game["used_side_titles"].add(event.get("title"))

    state: gc.GameState = game["state"]
    state.apply(effects)
    over = state.is_over()

    game["game_log"].append(f"[{event.get('title')}] {choice_text} → {result_text}")

    reaction = gc.get_character_reaction(state, effects, event.get("title", ""), choice_text)

    resp = {
        "state": _state_dict(state),
        "result_text": result_text,
        "reaction": reaction,
        "game_over": None,
    }

    if over:
        game["game_over"] = True
        title, desc = gc.EARLY_ENDINGS[over]
        resp["game_over"] = {"title": title, "desc": desc, "early": True}

    return jsonify(resp)


@app.route("/api/next", methods=["POST"])
def api_next():
    game = _get_game()
    if game["game_over"]:
        return jsonify({"error": "게임이 이미 종료되었습니다."}), 400

    state: gc.GameState = game["state"]
    is_side = game["current_is_side"]

    if not is_side and random.random() < gc.SIDE_EVENT_TRIGGER_CHANCE:
        state.month_index += 1
        side = gc.ai_generate_side_event(state, game["used_side_titles"])
        if side is None:
            side = gc.pick_random_side_event(game["used_side_titles"])
        game["current_event"] = side
        game["current_is_side"] = True
        return jsonify({
            "state": _state_dict(state),
            "event": _event_dict(side, True),
            "ending": None,
        })

    if not is_side:
        state.month_index += 1

    if state.month_index >= len(gc.MAIN_EVENTS):
        title, desc, best, worst, avg = gc.compute_ending(state)
        ai_ending = gc.ai_generate_ending(state, game["principal_name"], game["game_log"])
        if ai_ending:
            title, desc = ai_ending
        game["game_over"] = True
        return jsonify({
            "state": _state_dict(state),
            "event": None,
            "ending": {
                "title": title, "desc": desc,
                "best": gc.STAT_LABELS.get(best, best),
                "worst": gc.STAT_LABELS.get(worst, worst),
                "avg": round(avg, 1),
            },
        })

    event = gc.MAIN_EVENTS[state.month_index]
    game["current_event"] = event
    game["current_is_side"] = False
    return jsonify({
        "state": _state_dict(state),
        "event": _event_dict(event, False),
        "ending": None,
    })


@app.route("/api/restart", methods=["POST"])
def api_restart():
    sid = session.get("sid")
    if sid and sid in GAMES:
        del GAMES[sid]
    return jsonify({"ok": True})


@app.route("/api/test-gemini", methods=["GET"])
def api_test_gemini():
    ok, msg = gc.test_gemini_connection()
    return jsonify({"ok": ok, "message": msg})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
