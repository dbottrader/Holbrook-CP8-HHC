#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════
  ASIN-HHC ↔ CP8/CP9 UNIFIED AUTONOMOUS BRIDGE v2.0
  24/7 Agent Runtime + Crypto Kernel + Lattice Memory

  Bridges:
  • ASIN-HHC Lattice Memory (persistent provenance chain)
  • CP8/CP9 Crypto Kernel (minting, mining, deployment)
  • Git Sync (project repos)
  • LLM Brain (Claude → GPT-4o fallback)
  • Tool Executor (shell, files, HTTP)

  SHA-256: [AUTO-GENERATED ON DEPLOY]
  Built: 2026-05-22
═══════════════════════════════════════════════════════════════════
"""

import os, sys, json, time, hashlib, asyncio, subprocess, logging, threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import traceback

# ═════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═════════════════════════════════════════════════════════════════
CONFIG = {
    "agent_id": "ASIN-HHC-BRIDGE-002",
    "loop_interval_seconds": int(os.getenv("BRIDGE_INTERVAL", "300")),
    "state_file": os.getenv("BRIDGE_STATE", "lattice_state.json"),
    "log_file": os.getenv("BRIDGE_LOG", "bridge.log"),
    "max_memory_entries": 1000,
    "api_keys": {
        "openai": os.getenv("OPENAI_API_KEY", ""),
        "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
        "github": os.getenv("GITHUB_TOKEN", ""),
        "moonshot": os.getenv("MOONSHOT_API_KEY", ""),
    },
    "repos": {
        "asin_hhc": os.getenv("ASIN_REPO", ""),
        "cp8": os.getenv("CP8_REPO", ""),
        "kailasa": os.getenv("KAILASA_REPO", ""),
    },
    "local_paths": {
        "workspace": os.getenv("WORKSPACE", "./workspace"),
        "outputs": os.getenv("OUTPUTS", "./outputs"),
        "scripts": os.getenv("SCRIPTS", "./scripts"),
    },
    "cp8": {
        "enabled": os.getenv("CP8_ENABLED", "true").lower() == "true",
        "rpc": os.getenv("CP8_RPC", "http://localhost:8545"),
        "chain_id": int(os.getenv("CP8_CHAIN_ID", "1337")),
        "private_key": os.getenv("CP8_PRIVATE_KEY", ""),
        "address": os.getenv("CP8_ADDRESS", ""),
        "mining": os.getenv("CP8_MINING", "false").lower() == "true",
        "difficulty": int(os.getenv("CP8_DIFFICULTY", "4")),
        "threads": int(os.getenv("CP8_THREADS", "2")),
        "auto_mint": os.getenv("CP8_AUTO_MINT", "false").lower() == "true",
    }
}

# ═════════════════════════════════════════════════════════════════
# LATTICE MEMORY SYSTEM
# ═════════════════════════════════════════════════════════════════
class LatticeMemory:
    """Persistent state with SHA-256 provenance chain."""

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.state = self._load()
        self._ensure_schema()

    def _load(self) -> Dict:
        if self.filepath.exists():
            with open(self.filepath, "r") as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(self.filepath, "w") as f:
            json.dump(self.state, f, indent=2, default=str)

    def _hash(self, data: Any) -> str:
        return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:16]

    def _ensure_schema(self):
        defaults = {
            "agent_id": CONFIG["agent_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "cycle_count": 0,
            "memories": [],
            "tasks": {"pending": [], "active": None, "completed": [], "failed": []},
            "provenance_chain": [],
            "last_cycle_hash": "0" * 16,
            "project_links": {k: {"last_sync": None, "commits_ahead": 0} for k in CONFIG["repos"]},
            "cp8_state": {"blocks_mined": 0, "last_mint": None, "chain_valid": True},
            "external_state": {}
        }
        for key, val in defaults.items():
            self.state.setdefault(key, val)
        self._save()

    def log(self, event_type: str, payload: Dict, source: str = "bridge") -> str:
        entry = {
            "id": self._hash({"t": time.time(), "p": payload}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "source": source,
            "payload": payload,
            "prev_hash": self.state["last_cycle_hash"]
        }
        entry["hash"] = self._hash(entry)
        self.state["memories"].append(entry)
        self.state["last_cycle_hash"] = entry["hash"]
        if len(self.state["memories"]) > CONFIG["max_memory_entries"]:
            self.state["memories"] = self.state["memories"][-CONFIG["max_memory_entries"]:]
        self.state["provenance_chain"].append(entry["hash"])
        self._save()
        return entry["hash"]

    def add_task(self, task: Dict) -> str:
        task_id = self._hash(task)
        task["id"] = task_id
        task["created_at"] = datetime.now(timezone.utc).isoformat()
        task["status"] = "pending"
        self.state["tasks"]["pending"].append(task)
        self.log("task_created", {"task_id": task_id, "description": task.get("description", "")})
        self._save()
        return task_id

    def get_next_task(self) -> Optional[Dict]:
        if self.state["tasks"]["pending"]:
            task = self.state["tasks"]["pending"].pop(0)
            task["started_at"] = datetime.now(timezone.utc).isoformat()
            task["status"] = "active"
            self.state["tasks"]["active"] = task
            self._save()
            return task
        return None

    def complete_task(self, task_id: str, result: Any):
        active = self.state["tasks"]["active"]
        if active and active["id"] == task_id:
            active["completed_at"] = datetime.now(timezone.utc).isoformat()
            active["status"] = "completed"
            active["result"] = result
            self.state["tasks"]["completed"].append(active)
            self.state["tasks"]["active"] = None
            self.log("task_completed", {"task_id": task_id, "result": str(result)[:200]})
            self._save()

    def fail_task(self, task_id: str, error: str):
        active = self.state["tasks"]["active"]
        if active and active["id"] == task_id:
            active["failed_at"] = datetime.now(timezone.utc).isoformat()
            active["status"] = "failed"
            active["error"] = error
            self.state["tasks"]["failed"].append(active)
            self.state["tasks"]["active"] = None
            self.log("task_failed", {"task_id": task_id, "error": error})
            self._save()

    def get_context(self, n: int = 15) -> str:
        recent = self.state["memories"][-n:] if self.state["memories"] else []
        return json.dumps({
            "recent_events": recent,
            "pending_tasks": len(self.state["tasks"]["pending"]),
            "active_task": self.state["tasks"]["active"],
            "cycle_count": self.state["cycle_count"],
            "project_status": self.state["project_links"],
            "cp8_status": self.state["cp8_state"]
        }, indent=2, default=str)

# ═════════════════════════════════════════════════════════════════
# CP8 CRYPTO KERNEL
# ═════════════════════════════════════════════════════════════════
@dataclass
class Block:
    index: int
    timestamp: float
    data: Dict
    previous_hash: str
    nonce: int = 0
    hash: str = ""
    miner: str = ""

    def compute_hash(self) -> str:
        block_string = json.dumps({
            "index": self.index, "timestamp": self.timestamp,
            "data": self.data, "previous_hash": self.previous_hash,
            "nonce": self.nonce, "miner": self.miner
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def mine(self, difficulty: int):
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.compute_hash()

@dataclass
class Transaction:
    tx_id: str
    from_addr: str
    to_addr: str
    amount: float
    timestamp: float
    signature: str = ""
    status: str = "pending"

    def sign(self, private_key: str):
        payload = f"{self.from_addr}{self.to_addr}{self.amount}{self.timestamp}"
        self.signature = hashlib.sha256((payload + private_key).encode()).hexdigest()
        self.tx_id = hashlib.sha256((payload + self.signature).encode()).hexdigest()[:32]

class CP8Kernel:
    def __init__(self, memory: LatticeMemory):
        self.memory = memory
        self.chain: List[Block] = []
        self.pending_txs: List[Transaction] = []
        self.mining_active = False
        self.mining_stats = {"blocks_mined": 0, "total_hashes": 0, "start_time": None, "last_block_time": None}
        self._init_genesis()

    def _init_genesis(self):
        if not self.chain:
            genesis = Block(index=0, timestamp=time.time(),
                data={"message": "CP8 Genesis — ASIN-HHC Bridge Connected", "version": "2.0"},
                previous_hash="0" * 64, miner="ASIN-HHC-BRIDGE")
            genesis.hash = genesis.compute_hash()
            self.chain.append(genesis)
            self.memory.log("cp8_genesis", {"hash": genesis.hash, "index": 0}, "cp8")

    def get_latest(self) -> Block:
        return self.chain[-1]

    def add_tx(self, from_addr: str, to_addr: str, amount: float) -> str:
        tx = Transaction(tx_id="", from_addr=from_addr, to_addr=to_addr, amount=amount, timestamp=time.time())
        tx.sign(CONFIG["cp8"]["private_key"])
        self.pending_txs.append(tx)
        self.memory.log("cp8_tx", {"tx_id": tx.tx_id, "amount": amount, "to": to_addr[:20]}, "cp8")
        return tx.tx_id

    def mine_block(self, miner: Optional[str] = None) -> Optional[Block]:
        if not CONFIG["cp8"]["mining"]:
            return None
        miner_addr = miner or CONFIG["cp8"]["address"] or "ASIN-HHC-MINER"
        latest = self.get_latest()

        new_block = Block(
            index=len(self.chain), timestamp=time.time(),
            data={"transactions": [asdict(tx) for tx in self.pending_txs], "miner_reward": 50.0},
            previous_hash=latest.hash, miner=miner_addr
        )

        self.mining_active = True
        new_block.mine(CONFIG["cp8"]["difficulty"])
        self.mining_active = False

        self.chain.append(new_block)
        self.pending_txs = []
        self.mining_stats["blocks_mined"] += 1
        self.mining_stats["last_block_time"] = time.time()

        self.memory.state["cp8_state"]["blocks_mined"] = self.mining_stats["blocks_mined"]
        self.memory._save()
        self.memory.log("cp8_block", {"index": new_block.index, "hash": new_block.hash[:16], "nonce": new_block.nonce}, "cp8")
        return new_block

    def mint(self, to_address: str, amount: float) -> Dict:
        tx_id = self.add_tx("MINT", to_address, amount)
        if CONFIG["cp8"]["mining"]:
            self.mine_block()
        self.memory.state["cp8_state"]["last_mint"] = {"to": to_address[:20], "amount": amount, "time": time.time()}
        self.memory._save()
        self.memory.log("cp8_mint", {"to": to_address[:20], "amount": amount, "tx": tx_id}, "cp8")
        return {"tx_id": tx_id, "amount": amount, "block": len(self.chain) - 1}

    def status(self) -> Dict:
        return {
            "chain_length": len(self.chain), "latest": asdict(self.get_latest()),
            "pending_txs": len(self.pending_txs), "mining_active": self.mining_active,
            "stats": self.mining_stats, "difficulty": CONFIG["cp8"]["difficulty"],
            "wallet": CONFIG["cp8"]["address"][:20] if CONFIG["cp8"]["address"] else "not_set"
        }

    def verify(self) -> bool:
        for i in range(1, len(self.chain)):
            cur, prev = self.chain[i], self.chain[i-1]
            if cur.hash != cur.compute_hash() or cur.previous_hash != prev.hash:
                return False
        return True

    def export(self, path: str):
        data = {"chain": [asdict(b) for b in self.chain], "exported_at": datetime.now(timezone.utc).isoformat()}
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        self.memory.log("cp8_export", {"path": path, "blocks": len(self.chain)}, "cp8")

    def start_mining_loop(self):
        def miner():
            while CONFIG["cp8"]["mining"]:
                block = self.mine_block()
                if block:
                    print(f"⛏️ Block #{block.index} | {block.hash[:16]}... | Nonce: {block.nonce}")
                time.sleep(2)
        t = threading.Thread(target=miner, daemon=True)
        t.start()
        self.memory.log("cp8_mining_start", {"thread": t.ident}, "cp8")
        return t

# ═════════════════════════════════════════════════════════════════
# TOOL EXECUTOR
# ═════════════════════════════════════════════════════════════════
class ToolExecutor:
    def __init__(self, memory: LatticeMemory, cp8: CP8Kernel):
        self.memory = memory
        self.cp8 = cp8
        self.workspace = Path(CONFIG["local_paths"]["workspace"])
        self.workspace.mkdir(parents=True, exist_ok=True)

    def shell(self, cmd: str, timeout: int = 60) -> Dict:
        self.memory.log("shell", {"cmd": cmd[:100]})
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=str(self.workspace))
            return {"success": r.returncode == 0, "stdout": r.stdout[:2000], "stderr": r.stderr[:1000], "code": r.returncode}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def git_sync(self, repo: str) -> Dict:
        url = CONFIG["repos"].get(repo)
        if not url:
            return {"success": False, "error": f"No repo: {repo}"}
        path = self.workspace / repo
        token = CONFIG["api_keys"]["github"]
        if path.exists():
            cmd = f"cd {path} && git pull origin main"
        else:
            auth = url.replace("https://", f"https://{token}@") if token else url
            cmd = f"cd {self.workspace} && git clone {auth} {repo}"
        result = self.shell(cmd)
        self.memory.state["project_links"][repo]["last_sync"] = datetime.now(timezone.utc).isoformat()
        self.memory._save()
        return result

    def write(self, filename: str, content: str) -> Dict:
        path = self.workspace / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        self.memory.log("file_write", {"file": filename, "size": len(content)})
        return {"success": True, "path": str(path)}

    def read(self, filename: str) -> Dict:
        path = self.workspace / filename
        if not path.exists():
            return {"success": False, "error": "Not found"}
        with open(path, "r") as f:
            c = f.read()
        return {"success": True, "content": c[:5000], "size": len(c)}

    def http(self, method: str, url: str, payload: Dict = None, headers: Dict = None) -> Dict:
        import urllib.request, urllib.error
        try:
            req = urllib.request.Request(url, method=method)
            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)
            if payload and method in ("POST", "PUT", "PATCH"):
                req.add_header("Content-Type", "application/json")
                req.data = json.dumps(payload).encode()
            with urllib.request.urlopen(req, timeout=30) as resp:
                return {"success": True, "status": resp.status, "body": resp.read().decode()[:5000]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cp8_call(self, action: str, params: Dict) -> Dict:
        """Execute CP8 kernel operations."""
        if not CONFIG["cp8"]["enabled"]:
            return {"success": False, "error": "CP8 disabled"}

        if action == "status":
            return {"success": True, "data": self.cp8.status()}
        elif action == "mine":
            block = self.cp8.mine_block(params.get("miner"))
            return {"success": True, "data": asdict(block) if block else {"message": "Mining off"}}
        elif action == "mint":
            return {"success": True, "data": self.cp8.mint(params.get("to", CONFIG["cp8"]["address"]), params.get("amount", 100))}
        elif action == "transfer":
            tx = self.cp8.add_tx(params.get("from", CONFIG["cp8"]["address"]), params.get("to"), params.get("amount", 0))
            return {"success": True, "tx_id": tx}
        elif action == "export":
            self.cp8.export(params.get("path", "cp8_chain.json"))
            return {"success": True}
        elif action == "verify":
            return {"success": self.cp8.verify(), "valid": self.cp8.verify()}
        elif action == "start_mining":
            CONFIG["cp8"]["mining"] = True
            t = self.cp8.start_mining_loop()
            return {"success": True, "thread": t.ident}
        elif action == "stop_mining":
            CONFIG["cp8"]["mining"] = False
            return {"success": True}
        else:
            return {"success": False, "error": f"Unknown CP8 action: {action}"}

# ═════════════════════════════════════════════════════════════════
# LLM BRAIN
# ═════════════════════════════════════════════════════════════════
class LLMBrain:
    def __init__(self, memory: LatticeMemory, cp8: CP8Kernel):
        self.memory = memory
        self.cp8 = cp8
        self.last_error = None

    def _call_anthropic(self, messages: List[Dict]) -> Optional[str]:
        key = CONFIG["api_keys"]["anthropic"]
        if not key:
            return None
        try:
            import anthropic
            c = anthropic.Anthropic(api_key=key)
            sys_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
            user_msgs = [m for m in messages if m["role"] != "system"]
            r = c.messages.create(model="claude-3-opus-20240229", max_tokens=4096, system=sys_msg, messages=user_msgs)
            return r.content[0].text
        except Exception as e:
            self.last_error = f"Anthropic: {e}"
            return None

    def _call_openai(self, messages: List[Dict]) -> Optional[str]:
        key = CONFIG["api_keys"]["openai"]
        if not key:
            return None
        try:
            import openai
            c = openai.OpenAI(api_key=key)
            r = c.chat.completions.create(model="gpt-4o", messages=messages, temperature=0.7)
            return r.choices[0].message.content
        except Exception as e:
            self.last_error = f"OpenAI: {e}"
            return None

    def think(self, context: str, directive: Optional[str] = None) -> Dict:
        cp8_status = json.dumps(self.cp8.status(), default=str, indent=2)[:300]

        system = f"""You are the ASIN-HHC Autonomous Bridge v2.0 with CP8 Crypto Kernel.
You operate 24/7. Analyze state, decide next action, output structured JSON.

AVAILABLE TOOLS:
- shell: execute commands
- git_sync: sync repos (asin_hhc, cp8, kailasa)
- write_file / read_file: file operations
- http_request: API calls
- cp8_status: get chain stats
- cp8_mine: mine a block
- cp8_mint: mint tokens (params: to, amount)
- cp8_transfer: send tokens
- cp8_start_mining / cp8_stop_mining: toggle mining
- cp8_export: export chain
- add_task: queue new task

CP8 STATUS: {cp8_status}

OUTPUT ONLY JSON:
{{"thought": "...", "action": "tool_name", "params": {{}}, "new_tasks": [{{"description": "", "priority": 1}}], "should_continue": true}}"""

        user = (
            f"Context:\n{context}\n"
        )
        if directive:
            user += f"\nDIRECTIVE: {directive}\n"
        user += "\nWhat next?"

        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        raw = self._call_anthropic(messages) or self._call_openai(messages)

        if not raw:
            return {"thought": f"LLM down. Error: {self.last_error}", "action": "shell", "params": {"command": "echo 'bridge alive' && date"}, "new_tasks": [], "should_continue": True}

        try:
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            return json.loads(raw.strip())
        except Exception as e:
            self.memory.log("llm_parse_error", {"raw": raw[:300], "error": str(e)})
            return {"thought": "Parse failed. Continuing.", "action": "shell", "params": {"command": "echo 'parse error recovered'"}, "new_tasks": [], "should_continue": True}

# ═════════════════════════════════════════════════════════════════
# MAIN BRIDGE
# ═════════════════════════════════════════════════════════════════
class Bridge:
    def __init__(self):
        self.memory = LatticeMemory(CONFIG["state_file"])
        self.cp8 = CP8Kernel(self.memory)
        self.tools = ToolExecutor(self.memory, self.cp8)
        self.brain = LLMBrain(self.memory, self.cp8)
        self.running = False
        logging.basicConfig(filename=CONFIG["log_file"], level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(message)s")
        self.logger = logging.getLogger("bridge")

    def _execute(self, decision: Dict) -> Dict:
        action = decision.get("action", "shell")
        params = decision.get("params", {})

        if action == "shell":
            return self.tools.shell(params.get("command", "echo noop"))
        elif action == "git_sync":
            return self.tools.git_sync(params.get("repo", "asin_hhc"))
        elif action == "write_file":
            return self.tools.write(params.get("filename"), params.get("content", ""))
        elif action == "read_file":
            return self.tools.read(params.get("filename"))
        elif action == "http_request":
            return self.tools.http(params.get("method", "GET"), params.get("url", ""), params.get("payload"), params.get("headers"))
        elif action.startswith("cp8_"):
            return self.tools.cp8_call(action.replace("cp8_", ""), params)
        elif action == "add_task":
            return {"success": True, "task_id": self.memory.add_task(params)}
        elif action == "complete_task":
            self.memory.complete_task(params.get("task_id"), params.get("result"))
            return {"success": True}
        else:
            return {"success": False, "error": f"Unknown: {action}"}

    def cycle(self, directive: Optional[str] = None):
        self.memory.state["cycle_count"] += 1
        n = self.memory.state["cycle_count"]
        self.logger.info(f"=== CYCLE {n} ===")

        context = self.memory.get_context(15)
        if self.memory.state["tasks"]["active"]:
            context += f"\n\nACTIVE: {json.dumps(self.memory.state['tasks']['active'], default=str)}"

        self.logger.info("Thinking...")
        decision = self.brain.think(context, directive)
        self.logger.info(f"Action: {decision.get('action')} | {decision.get('thought', '')[:80]}")

        result = self._execute(decision)
        self.memory.log("cycle", {
            "cycle": n, "action": decision.get("action"),
            "thought": decision.get("thought", "")[:150],
            "success": result.get("success", False),
            "summary": str(result.get("stdout", result.get("data", result)))[:150]
        })

        for t in decision.get("new_tasks", []):
            self.memory.add_task(t)

        self.logger.info(f"Cycle {n} done. Pending: {len(self.memory.state['tasks']['pending'])}")
        return decision, result

    def run(self, cycles: Optional[int] = None, interval: Optional[int] = None):
        self.running = True
        interval = interval or CONFIG["loop_interval_seconds"]
        self.logger.info(f"BRIDGE v2.0 STARTED | Agent: {CONFIG['agent_id']} | CP8: {CONFIG['cp8']['enabled']} | Interval: {interval}s")
        self.memory.log("bridge_start", {"cp8_enabled": CONFIG["cp8"]["enabled"], "interval": interval})

        count = 0
        try:
            while self.running:
                if cycles and count >= cycles:
                    break
                count += 1
                try:
                    self.cycle()
                except Exception as e:
                    self.logger.error(traceback.format_exc())
                    self.memory.log("cycle_error", {"error": str(e), "trace": traceback.format_exc()[:400]})
                if self.running and (not cycles or count < cycles):
                    time.sleep(interval)
        except KeyboardInterrupt:
            self.logger.info("Interrupted")
        finally:
            self.memory.log("bridge_stop", {"cycles": count})
            self.logger.info(f"STOPPED | Cycles: {count}")

    def stop(self):
        self.running = False

# ═════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ASIN-HHC ↔ CP8 Unified Bridge v2.0")
    parser.add_argument("--run", action="store_true", help="Infinite loop")
    parser.add_argument("--cycle", action="store_true", help="Single cycle")
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--directive", type=str)
    parser.add_argument("--state", type=str, default="lattice_state.json")
    parser.add_argument("--cp8-mine", action="store_true", help="Mine one block now")
    parser.add_argument("--cp8-mint", type=str, help="Mint to address")
    parser.add_argument("--cp8-amount", type=float, default=100.0)
    parser.add_argument("--cp8-status", action="store_true")
    parser.add_argument("--cp8-start-mining", action="store_true")
    args = parser.parse_args()

    CONFIG["loop_interval_seconds"] = args.interval
    CONFIG["state_file"] = args.state

    bridge = Bridge()

    # CP8 direct commands
    if args.cp8_status:
        print(json.dumps(bridge.cp8.status(), indent=2, default=str))
    if args.cp8_mine:
        CONFIG["cp8"]["mining"] = True
        b = bridge.cp8.mine_block()
        print(f"Mined #{b.index} | {b.hash} | Nonce: {b.nonce}")
    if args.cp8_mint:
        r = bridge.cp8.mint(args.cp8_mint, args.cp8_amount)
        print(f"Minted {args.cp8_amount} to {args.cp8_mint} | TX: {r['tx_id']}")
    if args.cp8_start_mining:
        CONFIG["cp8"]["mining"] = True
        bridge.cp8.start_mining_loop()
        print("Mining loop started. Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopped.")

    # Bridge modes
    if args.cycle:
        d, r = bridge.cycle(directive=args.directive)
        print(json.dumps({"decision": d, "result": r}, indent=2, default=str))
    elif args.run:
        bridge.run(interval=args.interval)
    elif not any([args.cp8_status, args.cp8_mine, args.cp8_mint, args.cp8_start_mining]):
        print("ASIN-HHC ↔ CP8 UNIFIED BRIDGE v2.0")
        print(f"State: {args.state} | Pending: {len(bridge.memory.state['tasks']['pending'])} | Memories: {len(bridge.memory.state['memories'])}")
        print(f"CP8 Chain: {len(bridge.cp8.chain)} blocks | Mining: {CONFIG['cp8']['mining']}")
        print(f"\nUsage:")
        print(f"  python bridge.py --run --interval 60          # 24/7 daemon")
        print(f"  python bridge.py --cycle --directive '...'    # Single cycle")
        print(f"  python bridge.py --cp8-mine                   # Mine block")
        print(f"  python bridge.py --cp8-mint 0x... --amount 50 # Mint tokens")
        print(f"  python bridge.py --cp8-start-mining           # Background mining")
