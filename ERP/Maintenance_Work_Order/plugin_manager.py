"""
Plugin Hook Manager (Component B) — per-tenant extension architecture.

Each tenant may ship custom lifecycle logic in:

    plugins/tenant_<tenant_id>/hooks.py

defining any of the core lifecycle hooks:

    before_mwo_create(payload: dict) -> dict | None
        Validate or mutate an MWO payload before it is persisted. Returning a
        dict replaces the payload (re-validated by the caller); returning None
        leaves it untouched.
    after_mwo_created(mwo_id: str, mwo_data: dict) -> None
        Fire alerts / webhooks / external logging after an MWO is committed.
    after_inventory_consumed(sku_id: str, new_stock: int) -> None
        Run tenant-specific reorder logic after stock is decremented.

Design guarantees:
- A buggy or malicious tenant plugin can NEVER crash the core API request.
  Both load-time failures (syntax errors, bad imports) and run-time exceptions
  are caught, logged, and treated as a no-op.
- tenant_id is strictly validated (reusing the DNS-label allowlist that guards
  tenant DB paths) so a crafted id cannot traverse outside plugins/.
- Modules are cached per tenant so we import once, not on every request.
"""

import os
import importlib.util
import logging
import threading

from local_db import _validate_tenant_id

logger = logging.getLogger("PluginManager")

_here = os.path.dirname(os.path.abspath(__file__))
PLUGINS_DIR = os.path.join(_here, "plugins")

# The lifecycle hooks the core pipelines know how to invoke.
CORE_HOOKS = ("before_mwo_create", "after_mwo_created", "after_inventory_consumed")

# tenant_id -> loaded module (or None when absent/broken). None is a real cache
# entry: it means "we already looked and there is nothing usable", so we don't
# re-scan the filesystem on every request.
_module_cache = {}
_cache_lock = threading.Lock()


def _resolve_hooks_path(tenant_id: str) -> str:
    """Build the on-disk hooks.py path for a validated tenant, with a
    defence-in-depth containment check against the plugins root."""
    candidate = os.path.join(PLUGINS_DIR, f"tenant_{tenant_id}", "hooks.py")
    plugins_root = os.path.realpath(PLUGINS_DIR)
    resolved = os.path.realpath(candidate)
    if os.path.commonpath([plugins_root, resolved]) != plugins_root:
        raise ValueError(f"Resolved plugin path escapes plugins root: {tenant_id!r}")
    return resolved


def _load_tenant_hooks(tenant_id: str):
    """Import (once) and return the tenant's hooks module, or None if there is no
    plugin or it failed to load. Never raises."""
    if tenant_id in _module_cache:
        return _module_cache[tenant_id]

    with _cache_lock:
        if tenant_id in _module_cache:
            return _module_cache[tenant_id]

        module = None
        try:
            hooks_path = _resolve_hooks_path(tenant_id)
            if os.path.isfile(hooks_path):
                spec = importlib.util.spec_from_file_location(
                    f"tenant_plugins.tenant_{tenant_id}.hooks", hooks_path
                )
                candidate = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(candidate)
                module = candidate
                logger.info("[PLUGIN] Loaded hooks for tenant '%s' from %s", tenant_id, hooks_path)
        except Exception as e:
            # Syntax error / bad import / anything at module load time: isolate it.
            logger.error("[PLUGIN] Failed to load hooks for tenant '%s': %s", tenant_id, e, exc_info=True)
            module = None

        _module_cache[tenant_id] = module
        return module


def trigger_tenant_hook(tenant_id, hook_name: str, *args, **kwargs):
    """
    Invoke a tenant's lifecycle hook inside an isolated try-except boundary.

    Returns the hook's return value on success, or None when there is no tenant
    context, no plugin, no such hook, or the hook raised. The core API request
    is never affected — the worst case is a skipped hook.
    """
    if not tenant_id:
        return None

    try:
        tenant_id = _validate_tenant_id(tenant_id)
    except ValueError:
        logger.warning("[PLUGIN] Refusing hook '%s' for invalid tenant_id %r", hook_name, tenant_id)
        return None

    module = _load_tenant_hooks(tenant_id)
    if module is None:
        return None

    hook = getattr(module, hook_name, None)
    if not callable(hook):
        return None

    try:
        return hook(*args, **kwargs)
    except Exception as e:
        logger.error(
            "[PLUGIN] Hook '%s' for tenant '%s' raised and was suppressed: %s",
            hook_name, tenant_id, e, exc_info=True,
        )
        return None


def list_tenant_hooks(tenant_id) -> list:
    """Return the names of CORE_HOOKS the tenant's plugin actually defines (empty
    list if no/broken plugin). Used by the Concierge agent to report active hooks."""
    try:
        tenant_id = _validate_tenant_id(tenant_id)
    except (ValueError, TypeError):
        return []
    module = _load_tenant_hooks(tenant_id)
    if module is None:
        return []
    return [h for h in CORE_HOOKS if callable(getattr(module, h, None))]


def invalidate_tenant_hooks(tenant_id=None) -> None:
    """Drop cached hook modules so the next call re-scans disk. Pass a tenant_id
    to clear one tenant (e.g. after provisioning installs a new plugin), or None
    to clear all."""
    with _cache_lock:
        if tenant_id is None:
            _module_cache.clear()
        else:
            _module_cache.pop(tenant_id, None)
