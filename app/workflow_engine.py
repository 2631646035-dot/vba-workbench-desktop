"""
工作流引擎 - 解析YAML工作流定义，按顺序调度执行器

每个工作流由 YAML 文件定义，引擎负责：
1. 加载和解析工作流定义
2. 维护执行上下文（跨步骤传递数据）
3. 顺序执行步骤
4. 超时控制
5. 错误处理和日志记录
"""

import logging
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable

import yaml

logger = logging.getLogger("WorkflowEngine")


class StepResult:
    def __init__(self, success: bool, message: str = "", data: Any = None,
                 duration: float = 0.0):
        self.success = success
        self.message = message
        self.data = data or {}
        self.duration = duration

    def __repr__(self):
        status = "OK" if self.success else "FAIL"
        return f"StepResult({status}, {self.message[:60]})"


class WorkflowEngine:
    def __init__(self, settings: dict, executor_registry: dict):
        self.settings = settings
        self.executor_registry = executor_registry
        self.running = False
        self.paused = False
        self.cancelled = False
        self.context: Dict[str, Any] = {}
        self.on_step_start: Optional[Callable] = None
        self.on_step_end: Optional[Callable] = None
        self.on_log: Optional[Callable] = None
        self.on_workflow_end: Optional[Callable] = None

    def _log(self, msg: str, level: str = "INFO"):
        logger.info(msg)
        if self.on_log:
            self.on_log(msg, level)

    def load_all_workflows(self) -> List[dict]:
        workflows = []
        for path_str in self.settings.get("workflow_paths", []):
            wf_dir = Path(path_str)
            if not wf_dir.exists():
                logger.warning("Workflows directory not found: %s", wf_dir)
                continue
            for yaml_file in sorted(wf_dir.glob("*.yaml")):
                try:
                    with open(yaml_file, "r", encoding="utf-8") as f:
                        wf = yaml.safe_load(f)
                    wf["_file"] = str(yaml_file)
                    wf["_filename"] = str(yaml_file.name)
                    workflows.append(wf)
                except Exception as e:
                    logger.error("Failed to load %s: %s", yaml_file, e)
        return workflows

    def find_workflow_for_file(self, file_path: str) -> Optional[dict]:
        path = Path(file_path)
        all_wf = self.load_all_workflows()
        for wf in all_wf:
            trigger = wf.get("trigger", {})
            if trigger.get("type") == "file_watch":
                watch_path = Path(trigger.get("path", ""))
                try:
                    path.relative_to(watch_path)
                except ValueError:
                    continue
                pattern = trigger.get("pattern", "*")
                if path.match(pattern):
                    flt_cfg = trigger.get("filter", "")
                if flt_cfg:
                    filters = [f.strip() for f in flt_cfg.split("|")]
                    if not any(f.lower() in path.name.lower() for f in filters):
                        continue
                    return wf
        return None

    def run(self, workflow: dict, initial_context: dict = None) -> list:
        self.running = True
        self.paused = False
        self.cancelled = False
        self.context = initial_context or {}
        self.context["workflow_name"] = workflow.get("name", "Unknown")
        self.context["start_time"] = datetime.now()

        results = []
        steps = workflow.get("steps", [])
        self._log(f"Starting workflow: {workflow.get('name')} ({len(steps)} steps)")

        return self._run_steps(steps, results)

    def _run_steps(self, steps: list, results: list) -> list:
        for i, step in enumerate(steps):
            if self.cancelled:
                self._log("Workflow cancelled by user", "WARN")
                break

            while self.paused and not self.cancelled:
                time.sleep(0.2)

            step_name = step.get("name", f"Step{i + 1}")
            step_type = step.get("type")
            condition = step.get("condition")
            branch_true = step.get("branch_true")
            branch_false = step.get("branch_false")

            if condition:
                cond_result = eval(condition, {"__builtins__": {}}, self.context)
                if not cond_result:
                    if branch_false:
                        self._log(f"[BRANCH else] condition '{condition}' is False, taking else path")
                        self._run_steps(branch_false, results)
                        continue
                    else:
                        self._log(f"[SKIP] condition '{condition}' is False")
                        continue
                if branch_true:
                    self._log(f"[BRANCH then] condition '{condition}' is True, taking then path")
                    self._run_steps(branch_true, results)
                    continue

            self._log(f"[{i + 1}/{len(steps)}] {step_name} ({step_type})")

            if self.on_step_start:
                self.on_step_start(step_name, i, len(steps))

            executor = self.executor_registry.get(step_type)
            if executor is None:
                result = StepResult(False, f"Unknown step type: {step_type}")
                results.append(result)
                self._log(f"  FAIL: Unknown step type '{step_type}'", "ERROR")
                if self.on_step_end:
                    self.on_step_end(step_name, result)
                break

            start = time.time()
            try:
                result = self._execute_step_with_timeout(
                    executor, step.get("config", {}), step_type
                )
            except Exception as e:
                result = StepResult(False, str(e))
                self._log(f"  FAIL: {e}", "ERROR")

            result.duration = time.time() - start
            results.append(result)

            status = "OK" if result.success else "FAIL"
            self._log(f"  {status} ({result.duration:.1f}s) {result.message}")

            if self.on_step_end:
                self.on_step_end(step_name, result)

            if not result.success:
                self._log("Stopping workflow due to step failure", "WARN")
                break

        self.running = False
        total_duration = (datetime.now() - self.context["start_time"]).total_seconds()
        self._log(f"Workflow finished. "
                  f"{sum(1 for r in results if r.success)}/{len(results)} succeeded, "
                  f"total {total_duration:.1f}s")

        if self.on_workflow_end:
            self.on_workflow_end(results)

        return results

    def _execute_step_with_timeout(self, executor, config: dict, step_type: str) -> StepResult:
        timeouts = self.settings.get("timeouts", {})
        default_timeout = timeouts.get("step_default", 30) * 60
        timeout = timeouts.get(step_type, default_timeout / 60) * 60

        if step_type in ("run_python", "wps_macro"):
            result = executor(config, self.context)
        else:
            result = executor(config, self.context)

        return result

    def pause(self):
        self.paused = True
        self._log("Workflow paused")

    def resume(self):
        self.paused = False
        self._log("Workflow resumed")

    def cancel(self):
        self.cancelled = True
        self.paused = False
        self._log("Workflow cancelled")
