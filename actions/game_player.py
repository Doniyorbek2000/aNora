# actions/game_player.py
# Autonomous game playing — analyzes screen, makes decisions, controls gameplay

import time
import threading
import random
from pathlib import Path
from typing import Dict, List, Tuple, Optional

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

from actions.screen_processor import screen_process
from actions.computer_control import _click, _press, _move_mouse, _hotkey, _type_text

# Game-specific configurations
GAME_CONFIGS = {
    "pubg_mobile": {
        "app_name": "PUBG Mobile",
        "emulator": "LDPlayer",  # Common Android emulator
        "screen_regions": {
            "health_bar": (0.1, 0.9, 0.8, 0.95),  # x1,y1,x2,y2 as fractions
            "ammo_count": (0.85, 0.85, 0.95, 0.9),
            "minimap": (0.75, 0.05, 0.95, 0.25),
            "crosshair": (0.45, 0.45, 0.55, 0.55),
        },
        "controls": {
            "move_forward": "w",
            "move_back": "s",
            "move_left": "a",
            "move_right": "d",
            "jump": "space",
            "crouch": "ctrl",
            "prone": "z",
            "shoot": "left_click",
            "aim": "right_click",
            "reload": "r",
            "switch_weapon": "q",
            "use_item": "f",
            "open_map": "m",
        },
        "objectives": ["survive", "eliminate_enemies", "collect_loot", "win_match"],
    },
    "generic_fps": {
        "controls": {
            "move_forward": "w",
            "move_back": "s",
            "move_left": "a",
            "move_right": "d",
            "jump": "space",
            "shoot": "left_click",
            "aim": "right_click",
        },
        "objectives": ["explore", "combat", "survive"],
    },
}

class GameAI:
    def __init__(self, game_name: str = "pubg_mobile"):
        self.game_name = game_name
        self.config = GAME_CONFIGS.get(game_name, GAME_CONFIGS["generic_fps"])
        self.is_playing = False
        self.current_objective = None
        self.game_state = {}
        self.decision_history = []
        self.screen_analysis_cache = {}

    def start_game(self) -> str:
        """Launch the game or emulator."""
        from actions.open_app import open_app

        app_name = self.config.get("app_name", self.game_name)
        emulator = self.config.get("emulator")

        if emulator:
            # Try to launch emulator first
            result = open_app({"app_name": emulator})
            if "successfully" in result.lower():
                time.sleep(10)  # Wait for emulator to load
                # Then launch game within emulator
                result += f"\nLaunched {emulator}. Starting {app_name}..."
            else:
                return f"Could not launch emulator {emulator}: {result}"

        result = open_app({"app_name": app_name})
        if "successfully" not in result.lower():
            return f"Could not launch game {app_name}: {result}"

        time.sleep(15)  # Wait for game to load
        self.is_playing = True
        self.current_objective = random.choice(self.config["objectives"])
        return f"Game {app_name} launched. Starting autonomous play with objective: {self.current_objective}"

    def analyze_screen(self) -> Dict:
        """Analyze current game screen for state information."""
        try:
            # Use screen processor to analyze game screen
            analysis = screen_process({
                "angle": "screen",
                "text": f"Analyze this {self.game_name} game screen. Identify: player health, enemies visible, weapons, loot, current location, threats, objectives. Describe what you see in detail."
            })

            # Cache analysis for decision making
            self.screen_analysis_cache = {
                "timestamp": time.time(),
                "analysis": analysis,
                "game_state": self._extract_game_state(analysis)
            }

            return self.screen_analysis_cache

        except Exception as e:
            return {"error": f"Screen analysis failed: {e}"}

    def _extract_game_state(self, analysis: str) -> Dict:
        """Extract structured game state from screen analysis text."""
        state = {
            "health": 100,  # Default full health
            "ammo": 30,     # Default ammo
            "enemies_visible": 0,
            "threats": [],
            "loot_nearby": [],
            "current_location": "unknown",
            "objective_progress": 0
        }

        analysis_lower = analysis.lower()

        # Extract health (look for numbers near health indicators)
        if "health" in analysis_lower or "hp" in analysis_lower:
            # Simple pattern matching for health values
            import re
            health_match = re.search(r'(\d+)%?\s*(?:health|hp)', analysis_lower)
            if health_match:
                state["health"] = int(health_match.group(1))

        # Extract enemies
        if "enemy" in analysis_lower or "player" in analysis_lower:
            enemy_count = analysis_lower.count("enemy") + analysis_lower.count("player")
            state["enemies_visible"] = max(0, enemy_count - 1)  # Subtract self

        # Extract threats
        threat_keywords = ["enemy", "danger", "threat", "shooting", "gunfire"]
        state["threats"] = [kw for kw in threat_keywords if kw in analysis_lower]

        # Extract loot
        loot_keywords = ["weapon", "ammo", "armor", "loot", "item", "gun"]
        state["loot_nearby"] = [kw for kw in loot_keywords if kw in analysis_lower]

        return state

    def make_decision(self) -> Dict:
        """AI decision making based on current game state."""
        if not self.screen_analysis_cache:
            self.analyze_screen()

        state = self.screen_analysis_cache.get("game_state", {})
        analysis = self.screen_analysis_cache.get("analysis", "")

        decision = {
            "action": "explore",
            "reasoning": "Default exploration",
            "priority": "low",
            "controls": []
        }

        # Health-based decisions
        if state.get("health", 100) < 30:
            decision.update({
                "action": "retreat",
                "reasoning": f"Low health ({state['health']}%), need to find cover",
                "priority": "high",
                "controls": ["move_back", "crouch"]
            })

        # Combat decisions
        elif state.get("enemies_visible", 0) > 0:
            decision.update({
                "action": "combat",
                "reasoning": f"{state['enemies_visible']} enemies visible, engaging",
                "priority": "high",
                "controls": ["aim", "shoot"]
            })

        # Loot collection
        elif state.get("loot_nearby"):
            decision.update({
                "action": "loot",
                "reasoning": f"Found loot: {', '.join(state['loot_nearby'])}",
                "priority": "medium",
                "controls": ["move_forward", "use_item"]
            })

        # Exploration
        else:
            decision.update({
                "action": "explore",
                "reasoning": "No immediate threats or objectives, exploring",
                "priority": "low",
                "controls": ["move_forward", "look_around"]
            })

        # Add some randomness for more human-like behavior
        if random.random() < 0.1:  # 10% chance
            decision["controls"].append(random.choice(["jump", "crouch", "switch_weapon"]))

        self.decision_history.append(decision)
        return decision

    def execute_action(self, decision: Dict) -> str:
        """Execute the decided actions using computer control."""
        controls = decision.get("controls", [])
        executed = []

        for control in controls:
            try:
                if control in self.config.get("controls", {}):
                    key = self.config["controls"][control]
                    if key == "left_click":
                        _click(button="left")
                    elif key == "right_click":
                        _click(button="right")
                    elif key == "look_around":
                        # Random mouse movement
                        x = random.randint(100, 800)
                        y = random.randint(100, 600)
                        _move_mouse(x, y)
                    else:
                        _press(key)
                    executed.append(control)
                    time.sleep(random.uniform(0.1, 0.5))  # Human-like delay

                elif control == "wait":
                    time.sleep(random.uniform(1, 3))

            except Exception as e:
                executed.append(f"{control}(failed: {e})")

        return f"Executed: {', '.join(executed)}"

    def play_autonomously(self, duration_minutes: int = 10) -> str:
        """Main autonomous play loop."""
        if not self.is_playing:
            start_result = self.start_game()
            if "launched" not in start_result.lower():
                return start_result

        end_time = time.time() + (duration_minutes * 60)
        actions_taken = []

        while time.time() < end_time and self.is_playing:
            try:
                # Analyze situation
                analysis = self.analyze_screen()

                # Make decision
                decision = self.make_decision()

                # Execute action
                action_result = self.execute_action(decision)

                actions_taken.append(f"{decision['action']}: {action_result}")

                # Wait before next action
                time.sleep(random.uniform(2, 5))

                # Check if game is still running (basic check)
                if random.random() < 0.05:  # 5% chance to check
                    if not self._is_game_running():
                        self.is_playing = False
                        break

            except Exception as e:
                actions_taken.append(f"Error: {e}")
                time.sleep(5)

        summary = self._generate_summary(actions_taken)
        return f"Autonomous play completed.\n\nSummary:\n{summary}"

    def _is_game_running(self) -> bool:
        """Basic check if game is still running."""
        try:
            import psutil
            game_name = self.config.get("app_name", self.game_name).lower()
            for proc in psutil.process_iter(['name']):
                if game_name in proc.info['name'].lower():
                    return True
        except:
            pass
        return True  # Assume running if check fails

    def _generate_summary(self, actions: List[str]) -> str:
        """Generate a summary of the gameplay session."""
        total_actions = len(actions)
        decisions = [d for d in self.decision_history if isinstance(d, dict)]

        action_counts = {}
        for decision in decisions:
            action = decision.get("action", "unknown")
            action_counts[action] = action_counts.get(action, 0) + 1

        summary = f"""Gameplay Session Summary:
- Total actions taken: {total_actions}
- Decisions made: {len(decisions)}
- Action breakdown: {action_counts}
- Final objective: {self.current_objective}
- Session highlights: {random.choice(actions) if actions else 'No actions recorded'}"""

        return summary

    def stop_playing(self) -> str:
        """Stop autonomous play."""
        self.is_playing = False
        return "Autonomous gameplay stopped."

# Global game AI instance
_game_ai = None
_game_lock = threading.Lock()

def get_game_ai(game_name: str = "pubg_mobile") -> GameAI:
    """Get or create game AI instance."""
    global _game_ai
    with _game_lock:
        if _game_ai is None or _game_ai.game_name != game_name:
            _game_ai = GameAI(game_name)
    return _game_ai

def game_player(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None
) -> str:
    """
    Autonomous game playing system.

    parameters:
        action: start | play | analyze | decide | execute | stop
        game_name: pubg_mobile | generic_fps (default: pubg_mobile)
        duration_minutes: How long to play autonomously (default: 10)
    """
    params = parameters or {}
    action = params.get("action", "play").lower()
    game_name = params.get("game_name", "pubg_mobile")

    ai = get_game_ai(game_name)

    try:
        if action == "start":
            return ai.start_game()

        elif action == "play":
            duration = params.get("duration_minutes", 10)
            return ai.play_autonomously(duration)

        elif action == "analyze":
            analysis = ai.analyze_screen()
            return f"Screen Analysis:\n{analysis}"

        elif action == "decide":
            decision = ai.make_decision()
            return f"Decision: {decision}"

        elif action == "execute":
            decision = ai.make_decision()
            result = ai.execute_action(decision)
            return f"Executed {decision['action']}: {result}"

        elif action == "stop":
            return ai.stop_playing()

        else:
            return f"Unknown action: {action}. Use: start, play, analyze, decide, execute, stop"

    except Exception as e:
        return f"Game player error: {e}"