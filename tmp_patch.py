import re
import os

with open('api.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add _save_checkpoint and loading logic before 'iteration = 1'
checkpoint_logic = '''
                # ── Phase 8: Session Checkpoint Mechanics ──
                import os
                checkpoint_dir = os.path.join("Boardroom_Exchange", "active_sessions")
                os.makedirs(checkpoint_dir, exist_ok=True)
                checkpoint_file = os.path.join(checkpoint_dir, f"{project_id}_state.json")

                def _save_checkpoint(last_agent: str):
                    coo = coo_agent.get_coo()
                    ledger = coo.get_ledger(project_id)
                    def serialize_report(rep):
                        if hasattr(rep, 'model_dump'):
                            return rep.model_dump()
                        elif hasattr(rep, 'dict'):
                            return rep.dict()
                        if isinstance(rep, dict):
                            return rep
                        return {}
                    
                    state = {
                        "last_agent": last_agent,
                        "coo": {
                            "tokens_in": ledger.tokens_in,
                            "tokens_out": ledger.tokens_out,
                            "iteration": ledger.iteration_count
                        },
                        "reports": {k: serialize_report(v) for k, v in _wr_session['reports'].items()}
                    }
                    try:
                        with open(checkpoint_file, "w", encoding="utf-8") as f:
                            json.dump(state, f, indent=2)
                    except Exception as e:
                        logger.warning(f"Failed writing checkpoint: {e}")

                if os.path.exists(checkpoint_file):
                    try:
                        with open(checkpoint_file, "r", encoding="utf-8") as f:
                            chk = json.load(f)
                        
                        coo_agent.get_coo().restore_ledger(
                            project_id,
                            chk['coo']['tokens_in'],
                            chk['coo']['tokens_out'],
                            chk['coo']['iteration']
                        )
                        
                        from warroom_protocol import WarRoomReport
                        for k, v in chk['reports'].items():
                            if 'metadata' not in v:
                                v['metadata'] = {}
                            v['metadata']['is_resumed'] = True
                            _wr_session['reports'][k] = WarRoomReport(**v)
                            
                        logger.info(f"Resumed debate {project_id} from {chk.get('last_agent', 'known')} checkpoint.")
                        asyncio.create_task(_broadcast({
                            "type": "dialogue",
                            "agent": "SYSTEM",
                            "icon": "💾",
                            "color": "#10b981",
                            "message": f"**[STATE RECOVERY]** Resuming debate from {chk.get('last_agent', 'previous')} checkpoint...",
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id))
                    except Exception as e:
                        logger.warning(f"Failed to load checkpoint: {e}")
'''
content = content.replace('                while iteration <= max_iterations:', checkpoint_logic + '\n                while iteration <= max_iterations:')

# CMO Replace
cmo_orig = '''
                    # 1a. CMO: Market Research + Cost Quantification
                    cmo_resp, cmo_data, cmo_meta = await trigger_agent_response('CMO', cmo_prompt_override)

                    # ── WAR ROOM: Parse CMO into typed WarRoomReport ──
                    cmo_report = parse_agent_response(cmo_resp, 'CMO', 'market', project_id, iteration, structured_data=cmo_data, metadata=cmo_meta)
                    _wr_store.save(cmo_report)
                    await _propose_wisdom(cmo_report)
                    _wr_session['reports']['CMO'] = cmo_report
                    cmo_hp = cmo_report.handoff_payload  # Strictly typed CMOHandoff fields'''
cmo_new = '''
                    # 1a. CMO: Market Research + Cost Quantification
                    if 'CMO' not in _wr_session['reports']:
                        cmo_resp, cmo_data, cmo_meta = await trigger_agent_response('CMO', cmo_prompt_override)

                        # ── WAR ROOM: Parse CMO into typed WarRoomReport ──
                        _cmo_report = parse_agent_response(cmo_resp, 'CMO', 'market', project_id, iteration, structured_data=cmo_data, metadata=cmo_meta)
                        _wr_store.save(_cmo_report)
                        await _propose_wisdom(_cmo_report)
                        _wr_session['reports']['CMO'] = _cmo_report
                        _save_checkpoint('CMO')

                    cmo_report = _wr_session['reports']['CMO']
                    cmo_hp = cmo_report.handoff_payload  # Strictly typed CMOHandoff fields'''
content = content.replace(cmo_orig, cmo_new)

# CEO Replace
ceo_orig = '''
                    ceo_resp, ceo_data, ceo_meta = await trigger_agent_response('CEO', ceo_handoff)

                    # ── WAR ROOM: Parse CEO into typed WarRoomReport ──
                    ceo_report = parse_agent_response(ceo_resp, 'CEO', 'validation', project_id, iteration, structured_data=ceo_data, metadata=ceo_meta)
                    _wr_store.save(ceo_report)
                    await _propose_wisdom(ceo_report)
                    _wr_session['reports']['CEO'] = ceo_report
                    ceo_hp = ceo_report.handoff_payload  # Strictly typed CEOHandoff fields'''
ceo_new = '''
                    if 'CEO' not in _wr_session['reports']:
                        ceo_resp, ceo_data, ceo_meta = await trigger_agent_response('CEO', ceo_handoff)

                        # ── WAR ROOM: Parse CEO into typed WarRoomReport ──
                        _ceo_report = parse_agent_response(ceo_resp, 'CEO', 'validation', project_id, iteration, structured_data=ceo_data, metadata=ceo_meta)
                        _wr_store.save(_ceo_report)
                        await _propose_wisdom(_ceo_report)
                        _wr_session['reports']['CEO'] = _ceo_report
                        _save_checkpoint('CEO')

                    ceo_report = _wr_session['reports']['CEO']
                    ceo_hp = ceo_report.handoff_payload  # Strictly typed CEOHandoff fields'''
content = content.replace(ceo_orig, ceo_new)

# CTO Replace
cto_orig = '''
                    cto_resp, cto_data, cto_meta = await trigger_agent_response('CTO', cto_handoff)

                    # ── WAR ROOM: Parse CTO into typed WarRoomReport ──
                    cto_report = parse_agent_response(cto_resp, 'CTO', 'technical', project_id, iteration, structured_data=cto_data, metadata=cto_meta)
                    _wr_store.save(cto_report)
                    await _propose_wisdom(cto_report)
                    _wr_session['reports']['CTO'] = cto_report
                    cto_hp = cto_report.handoff_payload  # Strictly typed CTOHandoff fields'''
cto_new = '''
                    if 'CTO' not in _wr_session['reports']:
                        cto_resp, cto_data, cto_meta = await trigger_agent_response('CTO', cto_handoff)

                        # ── WAR ROOM: Parse CTO into typed WarRoomReport ──
                        _cto_report = parse_agent_response(cto_resp, 'CTO', 'technical', project_id, iteration, structured_data=cto_data, metadata=cto_meta)
                        _wr_store.save(_cto_report)
                        await _propose_wisdom(_cto_report)
                        _wr_session['reports']['CTO'] = _cto_report
                        _save_checkpoint('CTO')

                    cto_report = _wr_session['reports']['CTO']
                    cto_hp = cto_report.handoff_payload  # Strictly typed CTOHandoff fields'''
content = content.replace(cto_orig, cto_new)

# CFO Replace
cfo_orig = '''
                    cfo_resp, cfo_data, cfo_meta = await trigger_agent_response('CFO', cfo_handoff)

                    # ── WAR ROOM: Parse CFO into typed WarRoomReport ──
                    cfo_report = parse_agent_response(cfo_resp, 'CFO', 'financial', project_id, iteration, structured_data=cfo_data, metadata=cfo_meta)
                    _wr_store.save(cfo_report)
                    await _propose_wisdom(cfo_report)
                    _wr_session['reports']['CFO'] = cfo_report
                    cfo_hp = cfo_report.handoff_payload'''
cfo_new = '''
                    if 'CFO' not in _wr_session['reports']:
                        cfo_resp, cfo_data, cfo_meta = await trigger_agent_response('CFO', cfo_handoff)

                        # ── WAR ROOM: Parse CFO into typed WarRoomReport ──
                        _cfo_report = parse_agent_response(cfo_resp, 'CFO', 'financial', project_id, iteration, structured_data=cfo_data, metadata=cfo_meta)
                        _wr_store.save(_cfo_report)
                        await _propose_wisdom(_cfo_report)
                        _wr_session['reports']['CFO'] = _cfo_report
                        _save_checkpoint('CFO')

                    cfo_report = _wr_session['reports']['CFO']
                    cfo_hp = cfo_report.handoff_payload'''
content = content.replace(cfo_orig, cfo_new)

# CRITIC Replace
critic_orig = '''
                    # ── WAR ROOM: Parse CRITIC into typed WarRoomReport ──
                    critic_report = parse_agent_response(critic_resp, 'CRITIC', 'review', project_id, iteration, structured_data=critic_data, metadata=critic_meta)
                    _wr_store.save(critic_report)
                    await _propose_wisdom(critic_report)
                    _wr_session['reports']['CRITIC'] = critic_report
'''
critic_new = '''
                    # ── WAR ROOM: Parse CRITIC into typed WarRoomReport ──
                    critic_report = parse_agent_response(critic_resp, 'CRITIC', 'review', project_id, iteration, structured_data=critic_data, metadata=critic_meta)
                    _wr_store.save(critic_report)
                    await _propose_wisdom(critic_report)
                    _wr_session['reports']['CRITIC'] = critic_report
                    
                    if os.path.exists(checkpoint_file):
                        try:
                            os.remove(checkpoint_file)
                            logger.info(f"Clear checkpoint {checkpoint_file} upon CRITIC completion.")
                        except Exception as e:
                            pass
'''
content = content.replace(critic_orig, critic_new)

with open('api.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("API modified.")
