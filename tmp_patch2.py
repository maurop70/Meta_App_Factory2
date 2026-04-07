import re

with open('api.py', 'r', encoding='utf-8') as f:
    text = f.read()

# CMO Block
cmo_orig = '''
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
                    cmo_hp = cmo_report.handoff_payload  # Strictly typed CMOHandoff fields

                    # Extract CMO's critical numbers from typed handoff
                    cmo_marketing_cost = cmo_hp.get("marketing_cost", 0)
                    cmo_projected_revenue = cmo_hp.get("projected_revenue", 0)
                    cmo_demographic_reach = cmo_hp.get("demographic_reach", 0)
                    cmo_cpa = cmo_hp.get("cost_per_acquisition", 0)
                    cmo_recommendation = cmo_report.recommendation
                    cmo_strategy = cmo_hp.get("market_strategy", cmo_report.detailed_report[:300]) if hasattr(cmo_report, 'detailed_report') else "N/A"
'''

cmo_new = '''
                    # 1a. CMO: Market Research + Cost Quantification
                    cmo_data = {}
                    if "CMO" in triage_list:
                        if 'CMO' not in _wr_session['reports']:
                            cmo_resp, cmo_data, cmo_meta = await trigger_agent_response('CMO', cmo_prompt_override)

                            # ── WAR ROOM: Parse CMO into typed WarRoomReport ──
                            _cmo_report = parse_agent_response(cmo_resp, 'CMO', 'market', project_id, iteration, structured_data=cmo_data, metadata=cmo_meta)
                            _wr_store.save(_cmo_report)
                            await _propose_wisdom(_cmo_report)
                            _wr_session['reports']['CMO'] = _cmo_report
                            _save_checkpoint('CMO')

                        cmo_report = _wr_session['reports']['CMO']
                        cmo_hp = cmo_report.handoff_payload  # Strictly typed CMOHandoff fields
                        cmo_data = cmo_hp

                        # Extract CMO's critical numbers from typed handoff
                        cmo_marketing_cost = cmo_hp.get("marketing_cost", 0)
                        cmo_projected_revenue = cmo_hp.get("projected_revenue", 0)
                        cmo_demographic_reach = cmo_hp.get("demographic_reach", 0)
                        cmo_cpa = cmo_hp.get("cost_per_acquisition", 0)
                        cmo_recommendation = cmo_report.recommendation
                        cmo_strategy = cmo_hp.get("market_strategy", cmo_report.detailed_report[:300] if hasattr(cmo_report, 'detailed_report') else "N/A")
                    else:
                        logger.info("COO: Skipping CMO per CEO Triage.")
                        cmo_marketing_cost = 0
                        cmo_projected_revenue = 0
                        cmo_demographic_reach = 0
                        cmo_cpa = 0
                        cmo_recommendation = "SKIPPED"
                        cmo_strategy = "N/A"
                        cmo_hp = {}
'''
if "cmo_strategy = cmo_hp.get(\"market_strategy\"," in text:
    # Use simple split replace to avoid fragile regex matching
    idx1 = text.find("# 1a. CMO: Market Research")
    idx2 = text.find("# 1b. CEO: Validate CMO strategy")
    if idx1 != -1 and idx2 != -1:
        text = text[:idx1] + cmo_new + text[idx2:]


# CEO Block
ceo_orig = '''
                    # 1b. CEO: Validate CMO strategy against growth targets
                    # Build handoff from upstream CMO report
                    ceo_handoff = _wr_orchestrator.build_handoff_context(
                        PipelineStep(agent_name='CEO', phase='validation', depends_on=['CMO']),
                        _wr_session['reports'],
                        req.message,
                        iteration=iteration,
                        market_pulse=market_pulse_data,
                        wisdom_vault=get_wisdom_vault(),
                    )
                    if 'CEO' not in _wr_session['reports']:
                        ceo_resp, ceo_data, ceo_meta = await trigger_agent_response('CEO', ceo_handoff)

                        # ── WAR ROOM: Parse CEO into typed WarRoomReport ──
                        _ceo_report = parse_agent_response(ceo_resp, 'CEO', 'validation', project_id, iteration, structured_data=ceo_data, metadata=ceo_meta)
                        _wr_store.save(_ceo_report)
                        await _propose_wisdom(_ceo_report)
                        _wr_session['reports']['CEO'] = _ceo_report
                        _save_checkpoint('CEO')

                    ceo_report = _wr_session['reports']['CEO']
                    ceo_hp = ceo_report.handoff_payload  # Strictly typed CEOHandoff fields

                    ceo_approved = ceo_hp.get("approved_for_phase2", True)
                    ceo_alignment = ceo_hp.get("growth_target_alignment", "UNKNOWN")
                    ceo_target = ceo_hp.get("growth_target_annual", 0)

                    if not ceo_approved:
                        await _broadcast({
                            "type": "dialogue",
                            "agent": "SYSTEM",
                            "icon": "⚠️",
                            "color": "#f59e0b",
                            "message": f"**Phase 1 GATE: CEO flags MISALIGNMENT**\\nAlignment: {ceo_alignment} | Growth Target: ${ceo_target:,.0f}\\nCMO must revise. Cycling back.",
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id)
'''

ceo_new = '''
                    # 1b. CEO: Validate CMO strategy against growth targets
                    ceo_alignment = "UNKNOWN"
                    if "CEO" in triage_list:
                        # Build handoff from upstream CMO report
                        ceo_handoff = _wr_orchestrator.build_handoff_context(
                            PipelineStep(agent_name='CEO', phase='validation', depends_on=['CMO']),
                            _wr_session['reports'],
                            req.message,
                            iteration=iteration,
                            market_pulse=market_pulse_data,
                            wisdom_vault=get_wisdom_vault(),
                        )
                        if 'CEO' not in _wr_session['reports']:
                            ceo_resp, ceo_data, ceo_meta = await trigger_agent_response('CEO', ceo_handoff)

                            # ── WAR ROOM: Parse CEO into typed WarRoomReport ──
                            _ceo_report = parse_agent_response(ceo_resp, 'CEO', 'validation', project_id, iteration, structured_data=ceo_data, metadata=ceo_meta)
                            _wr_store.save(_ceo_report)
                            await _propose_wisdom(_ceo_report)
                            _wr_session['reports']['CEO'] = _ceo_report
                            _save_checkpoint('CEO')

                        ceo_report = _wr_session['reports']['CEO']
                        ceo_hp = ceo_report.handoff_payload  # Strictly typed CEOHandoff fields

                        ceo_approved = ceo_hp.get("approved_for_phase2", True)
                        ceo_alignment = ceo_hp.get("growth_target_alignment", "UNKNOWN")
                        ceo_target = ceo_hp.get("growth_target_annual", 0)

                        if not ceo_approved:
                            await _broadcast({
                                "type": "dialogue",
                                "agent": "SYSTEM",
                                "icon": "⚠️",
                                "color": "#f59e0b",
                                "message": f"**Phase 1 GATE: CEO flags MISALIGNMENT**\\nAlignment: {ceo_alignment} | Growth Target: ${ceo_target:,.0f}\\nRevision required. Cycling back.",
                                "timestamp": _dt.now().isoformat()
                            }, project=project_id)
                    else:
                        logger.info("COO: Skipping CEO validation per CEO Triage.")
'''
idx1 = text.find("# 1b. CEO: Validate CMO strategy")
idx2 = text.find("# ═══════════════════════════════════════════════════\n                    # PHASE 1.5: THE ENGINEER — CTO")
if idx1 != -1 and idx2 != -1:
    text = text[:idx1] + ceo_new + "\n" + text[idx2:]


cpo_new = '''
                    # ═══════════════════════════════════════════════════
                    # PHASE 1.2: THE PRODUCT OFFICER — CPO
                    # ═══════════════════════════════════════════════════
                    if "CPO" in triage_list:
                        await _broadcast({
                            "type": "dialogue",
                            "agent": "SYSTEM",
                            "icon": "🎨",
                            "color": "#ec4899",
                            "message": f"**PHASE 1.2: THE PRODUCT OFFICER**\\nCPO evaluating Commerciability & UX Friction...",
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id)

                        cpo_handoff = f"Provide a MoSCoW prioritization and UX alignment report based on intention: '{req.message}'"
                        if 'CPO' not in _wr_session['reports']:
                            cpo_resp, cpo_data, cpo_meta = await trigger_agent_response('CPO', cpo_handoff)
                            _cpo_report = parse_agent_response(cpo_resp, 'CPO', 'product', project_id, iteration, structured_data=cpo_data, metadata=cpo_meta)
                            _wr_store.save(_cpo_report)
                            _wr_session['reports']['CPO'] = _cpo_report
                            _save_checkpoint('CPO')
                    else:
                        logger.info("COO: Skipping CPO per CEO Triage.")
'''
# Insert CPO before CTO
text = text.replace("# PHASE 1.5: THE ENGINEER — CTO", cpo_new + "                    # PHASE 1.5: THE ENGINEER — CTO")


cto_new = '''
                    # CTO receives CMO strategy + CEO validation via orchestrator handoff
                    cto_data = {}
                    cto_hp = {}
                    if "CTO" in triage_list:
                        cto_handoff = _wr_orchestrator.build_handoff_context(
                            PipelineStep(agent_name='CTO', phase='technical', depends_on=['CMO', 'CEO']),
                            _wr_session['reports'],
                            req.message,
                            iteration=iteration,
                            market_pulse=market_pulse_data,
                            wisdom_vault=get_wisdom_vault(),
                        )
                        if 'CTO' not in _wr_session['reports']:
                            cto_resp, cto_data, cto_meta = await trigger_agent_response('CTO', cto_handoff)

                            # ── WAR ROOM: Parse CTO into typed WarRoomReport ──
                            _cto_report = parse_agent_response(cto_resp, 'CTO', 'technical', project_id, iteration, structured_data=cto_data, metadata=cto_meta)
                            _wr_store.save(_cto_report)
                            await _propose_wisdom(_cto_report)
                            _wr_session['reports']['CTO'] = _cto_report
                            _save_checkpoint('CTO')

                        cto_report = _wr_session['reports']['CTO']
                        cto_hp = cto_report.handoff_payload  # Strictly typed CTOHandoff fields
                        cto_data = cto_hp
                        
                        # Extract CTO's Technical Feasibility Score + USE fields from typed handoff
                        cto_feasibility = float(cto_hp.get("technical_feasibility_score", 5))
                        cto_project_type = cto_hp.get("project_type", "DIGITAL")
                        cto_tech_stack = cto_hp.get("tech_stack", [])
                        cto_automation_layer = cto_hp.get("automation_monitoring_layer", "")
                        cto_skills_blocks = cto_hp.get("skills_library_blocks", [])
                        cto_timeline = cto_hp.get("implementation_timeline_weeks", 0)
                        cto_v3_compliance = cto_hp.get("v3_compliance", "UNKNOWN")
                        cto_pre_deploy = cto_hp.get("pre_deploy_gate_status", "UNKNOWN")
                        cto_recommendation = cto_report.recommendation
                        
                        # Extract CFO-ready metrics from typed CTO handoff (already flattened)
                        infra_cost = cto_hp.get("infrastructure_cost_estimate", 0)
                        dev_buffer = cto_hp.get("development_buffer_weeks", 0)
                        tech_debt_premium = cto_hp.get("tech_debt_risk_premium_pct", 0)
                        gate_source = cto_hp.get("gate_source", "aether_native" if PRE_DEPLOY_AVAILABLE else "llm_estimate")

                        # Compute development_buffer_weeks if LLM didn't provide it
                        if not dev_buffer and cto_timeline:
                            dev_buffer = round(cto_timeline * 1.5, 1) if cto_feasibility < 7 else cto_timeline

                        # TECHNICAL GATE CHECK via Orchestrator
                        _cto_gate_step = PipelineStep(agent_name='CTO', phase='technical', is_gate=True, gate_threshold=4.0)
                        _cto_gate_result = _wr_orchestrator.check_gate(_cto_gate_step, cto_report)
                        if not _cto_gate_result['passed']:
                            await _broadcast({
                                "type": "dialogue",
                                "agent": "SYSTEM",
                                "icon": "🛑",
                                "color": "#ef4444",
                                "message": f"**TECHNICAL GATE FAILURE**\\n{_cto_gate_result['reason']}\\nCFO modeling BLOCKED. CTO recommends: {cto_recommendation}.\\nRevision required.",
                                "timestamp": _dt.now().isoformat()
                            }, project=project_id)
                    else:
                        logger.info("COO: Skipping CTO per CEO Triage.")
                        cto_timeline = 0
                        dev_buffer = 0
                        infra_cost = 0
                        tech_debt_premium = 0
                        cto_pre_deploy = "UNKNOWN"
'''
idx1 = text.find("# CTO receives CMO strategy + CEO validation via orchestrator handoff")
idx2 = text.find("# ═══════════════════════════════════════════════════\n                    # PHASE 2: THE MODEL — CFO")
if idx1 != -1 and idx2 != -1:
    text = text[:idx1] + cto_new + "\n" + text[idx2:]


clo_new = '''
                    # ═══════════════════════════════════════════════════
                    # PHASE 1.8: THE LEGAL OFFICER — CLO
                    # ═══════════════════════════════════════════════════
                    if "CLO" in triage_list:
                        await _broadcast({
                            "type": "dialogue",
                            "agent": "SYSTEM",
                            "icon": "⚖️",
                            "color": "#64748b",
                            "message": f"**PHASE 1.8: THE LEGAL OFFICER**\\nCLO evaluating IP Security & Compliance...",
                            "timestamp": _dt.now().isoformat()
                        }, project=project_id)

                        clo_handoff = f"Provide a rapid IP mapping and compliance scan for intention: '{req.message}'"
                        if 'CLO' not in _wr_session['reports']:
                            clo_resp, clo_data, clo_meta = await trigger_agent_response('CLO', clo_handoff)
                            _clo_report = parse_agent_response(clo_resp, 'CLO', 'legal', project_id, iteration, structured_data=clo_data, metadata=clo_meta)
                            _wr_store.save(_clo_report)
                            _wr_session['reports']['CLO'] = _clo_report
                            _save_checkpoint('CLO')
                    else:
                        logger.info("COO: Skipping CLO per CEO Triage.")
'''
text = text.replace("# PHASE 2: THE MODEL — CFO", clo_new + "                    # PHASE 2: THE MODEL — CFO")

cfo_new = '''
                    # ── AETHER-NATIVE CFO EXCEL EXTRACTION ──────────────────
                    if "CFO" in triage_list:
                        # Run the mathematical generation using native python/pandas
                        native_cfo_msg = ""
                        try:
                            from cfo_excel_architect import get_cfo_architect
                            cfo_arch = get_cfo_architect()
                            cfo_native_result = cfo_arch.generate_business_plan(
                                project_id=project_id,
                                cmo_data=cmo_data,
                                cto_data=cto_data,
                                market_pulse=market_pulse_data
                            )
                            if cfo_native_result.get("status") == "success":
                                native_cfo_msg = (
                                    f"\\n\\n=== Native Excel Architect Output ===\\n"
                                    f"Generated File: {cfo_native_result.get('file_path')}\\n"
                                    f"IRR: {cfo_native_result.get('metrics', {}).get('irr_pct', '?')}%"
                                )
                        except Exception as e:
                            logger.warning(f"Native CFO architectural build failed: {e}")

                        cfo_handoff = _wr_orchestrator.build_handoff_context(
                            PipelineStep(agent_name='CFO', phase='financial', depends_on=['CMO', 'CTO']),
                            _wr_session['reports'],
                            req.message,
                            iteration=iteration,
                            market_pulse=market_pulse_data,
                            wisdom_vault=get_wisdom_vault(),
                        )
                        cfo_handoff += native_cfo_msg
                        
                        if 'CFO' not in _wr_session['reports']:
                            cfo_resp, cfo_data, cfo_meta = await trigger_agent_response('CFO', cfo_handoff)

                            # ── WAR ROOM: Parse CFO into typed WarRoomReport ──
                            _cfo_report = parse_agent_response(cfo_resp, 'CFO', 'financial', project_id, iteration, structured_data=cfo_data, metadata=cfo_meta)
                            _wr_store.save(_cfo_report)
                            await _propose_wisdom(_cfo_report)
                            _wr_session['reports']['CFO'] = _cfo_report
                            _save_checkpoint('CFO')

                        cfo_report = _wr_session['reports']['CFO']
                        cfo_hp = cfo_report.handoff_payload
                        cfo_roi = cfo_hp.get("projected_roi", "UNKNOWN")
                        cfo_burn = cfo_hp.get("burn_rate_monthly", 0)
                        
                        cfo_data = cfo_hp
                    else:
                        logger.info("COO: Skipping CFO per CEO Triage.")
                        cfo_data = {}

                    # ═══════════════════════════════════════════════════
                    # PHASE 3: THE GATEKEEPER — CRITIC
'''

idx1 = text.find("# ── AETHER-NATIVE CFO EXCEL EXTRACTION ──────────────────")
idx2 = text.find("# ═══════════════════════════════════════════════════\n                    # PHASE 3: THE GATEKEEPER — CRITIC")
if idx1 != -1 and idx2 != -1:
    text = text[:idx1] + cfo_new + "\n" + text[idx2:]


with open('api.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Patch 6.5 applied successfully.")
