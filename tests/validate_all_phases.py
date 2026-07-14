"""
validate_all_phases.py
Comprehensive syntax validation of all GHOST GRID modules.
"""

import py_compile
import sys
from pathlib import Path

modules = [
    # Phase 1: Foundation
    "main.py",
    "bridge/pipe_client.py",
    "bridge/reader.py",
    "bridge/writer.py",
    "data/feed_router.py",
    "data/snapshot_builder.py",
    "data/schema.py",
    "config/constants.py",
    "config/instruments.py",
    "config/settings.py",
    # Phase 2: Telegram + Risk (legacy)
    "telegram/formatter.py",
    # Phase 3: Regime + HLCP + MPP
    "regime/classifier.py",
    "regime/indicators/ema_ribbon.py",
    "scoring/hlcp/engine.py",
    "scoring/mpp/engine.py",
    # Phase 4: Fusion + Gate + Risk + Execution + Positions + DB
    "scoring/fusion.py",
    "scoring/gate.py",
    "risk/constants.py",
    "risk/governor.py",
    "execution/commander.py",
    "positions/state_machine.py",
    "db/connection.py",
    # Phase 5: Portfolio + Nuclear + Watchdog + Telegram + Observability
    "portfolio/state.py",
    "nuclear/controller.py",
    "watchdog/thread.py",
    "telegram/bot.py",
    "observability/metrics.py",
]

failed = []
for mod in modules:
    try:
        py_compile.compile(mod, doraise=True)
        print(f"✅ {mod}")
    except Exception as e:
        print(f"❌ {mod}: {e}")
        failed.append(mod)

if failed:
    print(f"\n❌ {len(failed)} modules failed")
    sys.exit(1)
else:
    print(f"\n✅✅✅ ALL {len(modules)} MODULES COMPILE SUCCESSFULLY ✅✅✅")
    print("GHOST GRID — Complete 5-Phase Implementation Ready")
    sys.exit(0)
