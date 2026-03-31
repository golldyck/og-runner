"""Static OG Runner service layer for Goldy model discovery and demo runs."""

from __future__ import annotations

import asyncio
import json
import re
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from time import monotonic
from typing import Any, Literal
from urllib.parse import quote
from urllib.parse import urljoin, urlparse

import numpy as np
import requests
from web3 import Web3

from app.core.config import settings

from app.schemas import InputField, LeaderboardEntry, ModelDefinition, ModelGuide, ModelUsageStat

try:
    import opengradient as og
except Exception:  # pragma: no cover - optional import in local dev
    og = None


@dataclass
class ExecutionResult:
    normalized_input: dict[str, Any]
    result: dict[str, Any]
    ai_explanation: str
    warnings: list[str]
    execution_mode: Literal["live", "demo"]
    transaction_hash: str | None = None


_LLM_COOLDOWN_SECONDS = 300
_llm_cooldown_until = 0.0


def _number_field(key: str, label: str, description: str, placeholder: str) -> InputField:
    return InputField(
        key=key,
        label=label,
        kind="number",
        description=description,
        placeholder=placeholder,
    )


MODEL_REGISTRY: dict[str, ModelDefinition] = {
    "governance-capture-risk-scorer": ModelDefinition(
        slug="governance-capture-risk-scorer",
        title="Governance Capture Risk Scorer",
        owner="Goldy",
        hub_url="https://hub.opengradient.ai/models/Goldy/Governance-Capture-Risk-Scorer",
        model_cid="E0LylwkIkEn3hobZGgNDYOu4LYEEM7g_MI564Shjvrw",
        category="Governance Risk",
        summary="Scores DAO and DeFi governance takeover risk from concentration, execution control, proposal manipulation, and market attack-surface signals.",
        input_key="features",
        input_shape="[1, 30]",
        result_keys=["governance_capture_pressure", "governance_capture_risk_score", "grade", "flags"],
        input_fields=[
            _number_field("top1_holder_share", "Top 1 Holder Share", "Largest governance holder share.", "0.12"),
            _number_field("top10_holder_share", "Top 10 Holder Share", "Combined top-10 voting share.", "0.51"),
            _number_field("insider_voting_share", "Insider Voting Share", "Team, treasury, or foundation voting share.", "0.22"),
            _number_field("proposal_quorum_fragility", "Proposal Quorum Fragility", "How easy quorum is to force or block.", "0.42"),
            _number_field("flashloan_vote_exposure", "Flashloan Vote Exposure", "Borrowed-voting attack exposure.", "0.12"),
            _number_field("borrowable_supply_share", "Borrowable Supply Share", "Share of token float borrowable on markets.", "0.16"),
        ],
        sample_input={
            "top1_holder_share": 0.12,
            "top5_holder_share": 0.34,
            "top10_holder_share": 0.51,
            "gini_voting_power": 0.78,
            "insider_voting_share": 0.22,
            "active_delegate_share": 0.27,
            "circulating_vote_ratio": 0.48,
            "multisig_signer_concentration": 0.40,
            "multisig_threshold_risk": 0.18,
            "upgrade_timelock_risk": 0.30,
            "admin_key_centralization": 0.25,
            "emergency_pause_abuse_risk": 0.20,
            "signer_overlap_risk": 0.22,
            "treasury_execution_centralization": 0.24,
            "guardian_override_risk": 0.16,
            "proposal_quorum_fragility": 0.42,
            "delegate_absenteeism": 0.28,
            "voter_participation_decay": 0.19,
            "flashloan_vote_exposure": 0.12,
            "proposal_turnout_volatility": 0.31,
            "proposal_cancel_risk": 0.14,
            "voting_window_fragility": 0.20,
            "proposal_latency_risk": 0.18,
            "borrowable_supply_share": 0.16,
            "dex_liquidity_concentration": 0.44,
            "slippage_1m_buy_risk": 0.21,
            "whale_inflow_spike": 0.17,
            "unlock_overhang_risk": 0.26,
            "lending_concentration_risk": 0.23,
            "governance_volume_spike": 0.19,
        },
        guide=ModelGuide(
            what_it_does="Tells you whether a protocol's governance can be captured by whales, insiders, multisig operators, or short-term attackers.",
            what_you_need=[
                "Token holder concentration data",
                "Governance participation or quorum weakness data",
                "Admin or multisig control context",
                "Borrow/liquidity attack-surface context",
            ],
            what_result_means=[
                "Higher score means more capture pressure.",
                "Flags highlight the exact governance weakness.",
                "Grade A-F translates the risk into a simple decision layer.",
            ],
            next_steps=[
                "Paste a DAO or protocol link and map the missing governance fields.",
                "Run demo input first to understand the output shape.",
                "Use the flags and dominant factors for a written risk report.",
            ],
        ),
    ),
    "cross-chain-bridge-risk-classifier": ModelDefinition(
        slug="cross-chain-bridge-risk-classifier",
        title="Cross-Chain Bridge Risk Classifier",
        owner="Goldy",
        hub_url="https://hub.opengradient.ai/models/Goldy/cross-chain-bridge-risk-classifier",
        model_cid="j-W26qqNhXJPccXksDhbuMLvAbugN2Mwp2FaFD1ZBKY",
        category="Bridge Risk",
        summary="Classifies bridge protocols into LOW, MEDIUM, HIGH, or CRITICAL risk using custody, technical, operational, liquidity, and incident-history signals.",
        input_key="bridge_features",
        input_shape="[1, 18]",
        result_keys=["risk_score", "risk_label", "risk_category", "breakdown"],
        input_fields=[
            _number_field("tvl_usd", "TVL USD", "Total value locked.", "500000000"),
            _number_field("num_audits", "Number of Audits", "Completed audits.", "4"),
            _number_field("multisig_threshold", "Multisig Threshold", "Required signers / total.", "0.75"),
            _number_field("time_lock_hours", "Timelock Hours", "Upgrade timelock duration.", "48"),
            _number_field("prior_incidents", "Prior Incidents", "Known security incidents.", "0"),
            _number_field("uses_zk_proof", "Uses ZK Proof", "1 if zk verification exists, else 0.", "0"),
        ],
        sample_input={
            "tvl_usd": 500000000,
            "bridge_age_days": 730,
            "num_audits": 4,
            "audit_score": 8.0,
            "multisig_threshold": 0.75,
            "num_signers": 9,
            "admin_key_centralization": 0.0,
            "time_lock_hours": 48,
            "chains_supported": 5,
            "daily_tx_volume": 10000,
            "liquidity_concentration": 0.3,
            "prior_incidents": 0,
            "incident_severity_max": 0,
            "bug_bounty_usd": 1000000,
            "uses_light_client": 1,
            "uses_zk_proof": 0,
            "validator_set_size": 100,
            "code_open_source": 1,
        },
        guide=ModelGuide(
            what_it_does="Measures how dangerous a bridge design is before a user sends assets through it.",
            what_you_need=[
                "Bridge TVL and operational maturity",
                "Audit and verification architecture details",
                "Custody design, timelocks, and signer setup",
                "Incident history and verification stack",
            ],
            what_result_means=[
                "Risk score is the headline number from 0 to 100.",
                "Risk category turns that into LOW to CRITICAL.",
                "Breakdown shows which risk dimension drives the score.",
            ],
            next_steps=[
                "Paste a bridge URL and prefill the manual fields.",
                "Benchmark the result against Wormhole, Stargate, or Ronin-style profiles.",
                "Use the breakdown to explain whether custody or technical design is the problem.",
            ],
        ),
    ),
    "defi-protocol-health-score": ModelDefinition(
        slug="defi-protocol-health-score",
        title="DeFi Protocol Health Score",
        owner="Goldy",
        hub_url="https://hub.opengradient.ai/models/Goldy/DeFi-Protocol-Health-Score",
        model_cid="T27q-dRR1hKStiWLLCu_bCJe0R2_KBqg_xf5t0xXX4c",
        category="Protocol Health",
        summary="Evaluates protocol safety across TVL health, smart contract security, decentralization, market activity, and treasury resilience.",
        input_key="features",
        input_shape="[1, 30]",
        result_keys=["health_score", "grade", "pillar_scores", "flags", "summary"],
        input_fields=[
            _number_field("tvl_usd", "TVL USD", "Current protocol TVL.", "150000000"),
            _number_field("audit_count", "Audit Count", "Independent audits completed.", "3"),
            _number_field("timelock_hours", "Timelock Hours", "Governance timelock duration.", "48"),
            _number_field("top10_holder_share", "Top 10 Holder Share", "Governance concentration.", "0.38"),
            _number_field("unique_users_30d", "Unique Users 30d", "Active protocol users.", "12400"),
            _number_field("treasury_runway_months", "Treasury Runway Months", "Estimated operational runway.", "36"),
        ],
        sample_input={
            "tvl_usd": 150000000,
            "tvl_7d_change": -0.05,
            "tvl_30d_change": 0.12,
            "tvl_30d_volatility": 0.04,
            "tvl_top3_pool_concentration": 0.45,
            "tvl_vs_sector_median": 2.3,
            "days_since_deploy": 520,
            "audit_count": 3,
            "auditor_tier": 3,
            "has_bug_bounty": 1,
            "bug_bounty_max_payout_usd": 500000,
            "is_upgradeable": 1,
            "timelock_hours": 48,
            "exploit_history_count": 0,
            "exploit_total_loss_usd": 0,
            "governance_token_gini": 0.72,
            "top10_holder_share": 0.38,
            "multisig_threshold": 0.6,
            "unique_governance_voters_30d": 340,
            "dao_proposals_90d": 8,
            "founding_team_token_share": 0.15,
            "volume_to_tvl_ratio_7d": 0.35,
            "unique_users_30d": 12400,
            "user_growth_rate_30d": 0.08,
            "token_liquidity_depth_usd": 2500000,
            "revenue_30d_usd": 420000,
            "revenue_to_tvl_ratio": 0.0028,
            "treasury_usd": 18000000,
            "treasury_runway_months": 36,
            "native_token_share_of_treasury": 0.30,
            "stablecoin_share_of_treasury": 0.55,
            "revenue_covers_opex": 1,
        },
        guide=ModelGuide(
            what_it_does="Produces a single health score for a DeFi protocol by combining safety, activity, decentralization, and treasury signals.",
            what_you_need=[
                "TVL trend and concentration data",
                "Audit, exploit, and upgradeability context",
                "Governance and admin decentralization data",
                "Revenue, user activity, and treasury runway",
            ],
            what_result_means=[
                "Higher score means a stronger protocol health profile.",
                "Pillar scores tell you which dimension is weak.",
                "Flags identify institutional-grade blockers such as no timelock or low runway.",
            ],
            next_steps=[
                "Run a protocol baseline and compare competitors.",
                "Use the pillar breakdown in diligence reports.",
                "Track how treasury and governance changes shift the score over time.",
            ],
        ),
    ),
    "stablecoin-depeg-risk-monitor": ModelDefinition(
        slug="stablecoin-depeg-risk-monitor",
        title="Stablecoin Depeg Risk Monitor",
        owner="Goldy",
        hub_url="https://hub.opengradient.ai/models/Goldy/Stablecoin-Depeg-Risk-Monitor",
        model_cid="9ySF0q9c0JXxFajs7ojdzWU0UoYf5vsuO_Wd3U86GAE",
        category="Stablecoin Risk",
        summary="Monitors stablecoin peg stress using reserve adequacy, market stress, liquidity depth, and on-chain velocity signals.",
        input_key="features",
        input_shape="[1, 20]",
        result_keys=["depeg_risk_score", "alert", "pillar_scores"],
        input_fields=[
            _number_field("collateral_ratio", "Collateral Ratio", "Backing / supply.", "1.50"),
            _number_field("reserve_change_7d", "Reserve Change 7d", "Reserve growth or drain.", "-0.05"),
            _number_field("peg_deviation_pct", "Peg Deviation %", "Current spot deviation from $1.", "0.002"),
            _number_field("dex_liquidity_usd", "DEX Liquidity USD", "Total stablecoin on-chain liquidity.", "85000000"),
            _number_field("whale_outflow_7d", "Whale Outflow 7d", "Large-holder exit pressure.", "0.02"),
            _number_field("transfer_volume_7d_change", "Transfer Volume 7d Change", "Velocity spike signal.", "0.12"),
        ],
        sample_input={
            "collateral_ratio": 1.50,
            "reserve_change_7d": -0.05,
            "peg_token_share": 0.10,
            "treasury_runway_days": 365,
            "mint_redeem_ratio_7d": 1.20,
            "peg_deviation_pct": 0.002,
            "peg_deviation_7d_max": 0.005,
            "dex_volume_7d_change": 0.15,
            "funding_rate_perps": 0.001,
            "cex_volume_7d_change": 0.08,
            "dex_liquidity_usd": 85000000,
            "pool_concentration": 0.45,
            "slippage_1m_usd": 0.004,
            "liquidity_7d_change": -0.03,
            "redemption_queue_usd": 2500000,
            "transfer_volume_7d_change": 0.12,
            "unique_senders_7d_change": 0.08,
            "whale_outflow_7d": 0.02,
            "bridge_outflow_7d": 0.005,
            "smart_contract_net_flow": -0.01,
        },
        guide=ModelGuide(
            what_it_does="Warns when a stablecoin is drifting toward a depeg event before the market fully prices it in.",
            what_you_need=[
                "Reserve and collateral coverage data",
                "Market premium or discount signals",
                "DEX liquidity and redemption queue data",
                "On-chain wallet flow velocity",
            ],
            what_result_means=[
                "Depeg score measures total peg stress.",
                "Alert converts the score into STABLE, WATCH, WARNING, or CRITICAL.",
                "Pillar scores separate reserve weakness from liquidity or bank-run behavior.",
            ],
            next_steps=[
                "Benchmark multiple stablecoins side by side.",
                "Use WARNING and CRITICAL thresholds for alerts.",
                "Pair the output with treasury or collateral policy changes.",
            ],
        ),
    ),
    "dex-liquidity-exit-risk-scorer": ModelDefinition(
        slug="dex-liquidity-exit-risk-scorer",
        title="DEX Liquidity Exit Risk Scorer",
        owner="Goldy",
        hub_url="https://hub.opengradient.ai/models/Goldy/DEX-Liquidity-Exit-Risk-Scorer",
        model_cid="LOCAL_DEX_LIQUIDITY_EXIT_RISK_SCORER_PENDING_RELEASE",
        category="DEX Liquidity Risk",
        summary="Scores how likely a DEX or pool is to lose usable liquidity under LP exits, emissions decay, concentration, and flow stress before traders fully react.",
        input_key="features",
        input_shape="[1, 24]",
        result_keys=["liquidity_exit_risk_score", "grade", "risk_level", "pillar_scores", "flags"],
        input_fields=[
            _number_field("pool_tvl_usd", "Pool TVL USD", "Current usable liquidity in the pool or venue.", "120000000"),
            _number_field("liquidity_7d_change", "Liquidity 7d Change", "Weekly growth or drain in liquidity.", "-0.08"),
            _number_field("lp_top10_share", "LP Top 10 Share", "Share of liquidity controlled by top LP wallets.", "0.58"),
            _number_field("slippage_100k_buy_pct", "Slippage 100k Buy %", "Estimated buy-side slippage for a $100k trade.", "0.012"),
            _number_field("emissions_to_fees_ratio", "Emissions to Fees Ratio", "How dependent the pool is on incentives vs real fees.", "1.8"),
            _number_field("whale_lp_exit_7d", "Whale LP Exit 7d", "Observed large LP withdrawal pressure.", "0.09"),
        ],
        sample_input={
            "pool_tvl_usd": 120000000,
            "liquidity_7d_change": -0.08,
            "liquidity_30d_change": -0.04,
            "lp_top10_share": 0.58,
            "treasury_lp_share": 0.12,
            "protocol_owned_liquidity_share": 0.21,
            "incentive_apr": 0.18,
            "fee_apr": 0.07,
            "emissions_30d_usd": 4200000,
            "emissions_to_fees_ratio": 1.8,
            "volume_tvl_ratio_7d": 0.46,
            "slippage_100k_buy_pct": 0.012,
            "slippage_100k_sell_pct": 0.015,
            "bridge_dependent_liquidity_share": 0.28,
            "whale_lp_exit_7d": 0.09,
            "net_swap_flow_7d": -0.06,
            "unique_lp_count": 1480,
            "top_pool_share_of_protocol": 0.42,
            "token_unlock_30d_usd": 18000000,
            "governance_timelock_hours": 48,
            "audit_count": 3,
            "exploit_history_count": 0,
            "oracle_dependency_score": 0.34,
            "correlated_asset_risk": 0.26,
        },
        guide=ModelGuide(
            what_it_does="Shows whether a DEX or liquidity venue is vulnerable to a sharp liquidity exit before spreads, slippage, and user behavior fully deteriorate.",
            what_you_need=[
                "Pool TVL, LP concentration, and protocol-owned liquidity share",
                "Fee versus incentive dependence",
                "Slippage, swap flow, and recent liquidity change",
                "Audit, timelock, and exploit-history context",
            ],
            what_result_means=[
                "Higher score means the venue is more exposed to LP flight and depth collapse.",
                "Pillar scores separate depth weakness from concentration, emissions dependence, and governance safety.",
                "Flags identify practical blockers such as whale exits, shallow depth, or no timelock.",
            ],
            next_steps=[
                "Compare multiple DEX venues or competing pools side by side.",
                "Use the score before routing treasury or market-making liquidity into a venue.",
                "Track whether incentives are masking a fragile fee profile.",
            ],
        ),
    ),
    "nft-wash-trading-detector": ModelDefinition(
        slug="nft-wash-trading-detector",
        title="NFT Wash Trading Detector",
        owner="Goldy",
        hub_url="https://hub.opengradient.ai/models/Goldy/nft-wash-trading-detector",
        model_cid="Xy7MKQls2BJ32O_d2Q4CRa6HJlrYaDKQ3r2B2q-mLmQ",
        category="NFT Market Integrity",
        summary="Scores NFT transactions for wash-trading probability using price, timing, wallet overlap, and wallet history signals.",
        input_key="nft_features",
        input_shape="(N, 6)",
        result_keys=["wash_probability", "verdict"],
        input_fields=[
            _number_field("price_eth", "Price ETH", "Transaction price.", "0.5"),
            _number_field("time_delta_sec", "Time Delta Sec", "Seconds since previous transaction.", "10"),
            _number_field("buyer_tx_count", "Buyer Tx Count", "Past buyer transaction count.", "3"),
            _number_field("seller_tx_count", "Seller Tx Count", "Past seller transaction count.", "2"),
            _number_field("wallet_overlap_score", "Wallet Overlap Score", "Prior buyer/seller interaction score.", "0.95"),
            _number_field("gas_paid_gwei", "Gas Paid Gwei", "Gas paid for the trade.", "5"),
        ],
        sample_input={
            "price_eth": 0.5,
            "time_delta_sec": 10.0,
            "buyer_tx_count": 3.0,
            "seller_tx_count": 2.0,
            "wallet_overlap_score": 0.95,
            "gas_paid_gwei": 5.0,
        },
        guide=ModelGuide(
            what_it_does="Labels NFT transactions as likely wash trading or legitimate based on suspicious wallet overlap and trading cadence.",
            what_you_need=[
                "Transaction price and time spacing",
                "Buyer and seller wallet history",
                "Wallet overlap or prior interaction score",
                "Gas behavior for the transaction",
            ],
            what_result_means=[
                "Wash probability above 0.5 is suspicious.",
                "Wallet overlap is the strongest signal in the model.",
                "You can score a sequence or a single transaction row.",
            ],
            next_steps=[
                "Use it to filter fake marketplace volume.",
                "Compare suspicious collections against healthy ones.",
                "Feed wallet overlap features from your own analytics pipeline.",
            ],
        ),
    ),
}


BRIDGE_LEADERBOARD_PROFILES: list[dict[str, Any]] = [
    {
        "name": "Across",
        "protocol_url": "https://across.to",
        "summary": "Lean bridge profile with strong audit posture, long timelock, and no public major incident history.",
        "overrides": {
            "tvl_usd": 410_000_000,
            "bridge_age_days": 980,
            "num_audits": 6,
            "audit_score": 9.1,
            "multisig_threshold": 0.82,
            "num_signers": 11,
            "admin_key_centralization": 0.10,
            "time_lock_hours": 72,
            "chains_supported": 18,
            "daily_tx_volume": 32_000,
            "liquidity_concentration": 0.26,
            "prior_incidents": 0,
            "incident_severity_max": 0,
            "bug_bounty_usd": 2_000_000,
            "uses_light_client": 1,
            "uses_zk_proof": 1,
            "validator_set_size": 140,
            "code_open_source": 1,
        },
    },
    {
        "name": "Stargate",
        "protocol_url": "https://stargate.finance",
        "summary": "Large cross-chain liquidity network with strong operational maturity but broader custody and liquidity surface area.",
        "overrides": {
            "tvl_usd": 470_000_000,
            "bridge_age_days": 1_050,
            "num_audits": 5,
            "audit_score": 8.7,
            "multisig_threshold": 0.74,
            "num_signers": 9,
            "admin_key_centralization": 0.16,
            "time_lock_hours": 48,
            "chains_supported": 25,
            "daily_tx_volume": 51_000,
            "liquidity_concentration": 0.33,
            "prior_incidents": 0,
            "incident_severity_max": 0,
            "bug_bounty_usd": 1_500_000,
            "uses_light_client": 0,
            "uses_zk_proof": 1,
            "validator_set_size": 95,
            "code_open_source": 1,
        },
    },
    {
        "name": "Polygon Bridge",
        "protocol_url": "https://portal.polygon.technology/bridge",
        "summary": "Canonical bridge with meaningful scale, moderate custody assumptions, and solid but not minimal operational risk.",
        "overrides": {
            "tvl_usd": 830_000_000,
            "bridge_age_days": 1_450,
            "num_audits": 4,
            "audit_score": 8.4,
            "multisig_threshold": 0.68,
            "num_signers": 8,
            "admin_key_centralization": 0.22,
            "time_lock_hours": 36,
            "chains_supported": 9,
            "daily_tx_volume": 41_000,
            "liquidity_concentration": 0.40,
            "prior_incidents": 0,
            "incident_severity_max": 0,
            "bug_bounty_usd": 1_000_000,
            "uses_light_client": 0,
            "uses_zk_proof": 0,
            "validator_set_size": 70,
            "code_open_source": 1,
        },
    },
    {
        "name": "Hop Protocol",
        "protocol_url": "https://hop.exchange",
        "summary": "Older bridge design with decent signer setup, but weaker verification assumptions and smaller validator depth.",
        "overrides": {
            "tvl_usd": 185_000_000,
            "bridge_age_days": 1_180,
            "num_audits": 4,
            "audit_score": 8.1,
            "multisig_threshold": 0.71,
            "num_signers": 7,
            "admin_key_centralization": 0.18,
            "time_lock_hours": 24,
            "chains_supported": 8,
            "daily_tx_volume": 12_000,
            "liquidity_concentration": 0.37,
            "prior_incidents": 0,
            "incident_severity_max": 0,
            "bug_bounty_usd": 600_000,
            "uses_light_client": 0,
            "uses_zk_proof": 0,
            "validator_set_size": 42,
            "code_open_source": 1,
        },
    },
    {
        "name": "Synapse",
        "protocol_url": "https://synapseprotocol.com",
        "summary": "Broadly integrated bridge with moderate decentralization but higher operational complexity and more exposed trust surface.",
        "overrides": {
            "tvl_usd": 260_000_000,
            "bridge_age_days": 1_120,
            "num_audits": 3,
            "audit_score": 7.7,
            "multisig_threshold": 0.66,
            "num_signers": 6,
            "admin_key_centralization": 0.24,
            "time_lock_hours": 18,
            "chains_supported": 16,
            "daily_tx_volume": 15_000,
            "liquidity_concentration": 0.44,
            "prior_incidents": 1,
            "incident_severity_max": 0.25,
            "bug_bounty_usd": 500_000,
            "uses_light_client": 0,
            "uses_zk_proof": 0,
            "validator_set_size": 28,
            "code_open_source": 1,
        },
    },
    {
        "name": "Wormhole",
        "protocol_url": "https://wormhole.com",
        "summary": "High-throughput bridge with major historical incident baggage that keeps its leaderboard risk elevated despite scale.",
        "overrides": {
            "tvl_usd": 920_000_000,
            "bridge_age_days": 1_260,
            "num_audits": 4,
            "audit_score": 8.2,
            "multisig_threshold": 0.61,
            "num_signers": 19,
            "admin_key_centralization": 0.29,
            "time_lock_hours": 12,
            "chains_supported": 30,
            "daily_tx_volume": 68_000,
            "liquidity_concentration": 0.47,
            "prior_incidents": 1,
            "incident_severity_max": 1,
            "bug_bounty_usd": 2_500_000,
            "uses_light_client": 0,
            "uses_zk_proof": 0,
            "validator_set_size": 19,
            "code_open_source": 1,
        },
    },
]

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BRIDGE_RUNS_PATH = DATA_DIR / "bridge_runs.json"
MODEL_RUNS_PATH = DATA_DIR / "model_runs.json"
_REMOTE_MODEL_CACHE: dict[str, ModelDefinition] = {}


def _parse_hub_model_ref(model_ref: str) -> tuple[str, str] | None:
    normalized = model_ref.strip()
    if not normalized:
        return None

    hub_match = re.search(r"hub\.opengradient\.ai/models/([^/]+)/([^/?#]+)", normalized, flags=re.IGNORECASE)
    if hub_match:
        return hub_match.group(1), hub_match.group(2)

    if re.fullmatch(r"[^/\s]+/[^/\s]+", normalized):
        author, name = normalized.split("/", 1)
        return author, name

    return None


def _fetch_remote_model_definition(author: str, name: str) -> ModelDefinition:
    cache_key = f"{author}/{name}".lower()
    cached = _REMOTE_MODEL_CACHE.get(cache_key)
    if cached:
        return cached

    response = requests.get(
        f"https://hub-api.opengradient.ai/api/v0/models/{quote(name, safe='')}",
        params={"authorUsername": author},
        timeout=10,
        headers={"User-Agent": "OG-Runner/0.1"},
    )
    if response.status_code == 404:
        raise KeyError(f"Unknown model reference: {author}/{name}")
    response.raise_for_status()
    payload = response.json()
    model = _build_remote_model_definition(payload)
    _REMOTE_MODEL_CACHE[cache_key] = model
    return model


def _slugify_model_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _humanize_key(key: str) -> str:
    return re.sub(r"\s+", " ", key.replace("_", " ").replace("-", " ")).strip().title()


def _strip_markdown(text: str) -> str:
    cleaned = re.sub(r"`([^`]+)`", r"\1", text)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        heading = re.match(r"^\s{0,3}#{2,3}\s+(.+?)\s*$", line)
        if heading:
            current = heading.group(1).strip().lower()
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _section_by_names(sections: dict[str, str], *names: str) -> str:
    for key, value in sections.items():
        if any(name.lower() in key for name in names):
            return value
    return ""


def _extract_json_object(section: str) -> dict[str, Any]:
    if not section:
        return {}

    fence_match = re.search(r"```(?:json|python)?\s*(\{.*?\})\s*```", section, flags=re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except Exception:
            pass

    indented_lines: list[str] = []
    collecting = False
    for line in section.splitlines():
        if re.match(r"^\s{4,}\{", line):
            collecting = True
        if collecting:
            if line.startswith("    ") or line.startswith("\t") or not line.strip():
                indented_lines.append(line[4:] if line.startswith("    ") else line.lstrip("\t"))
                continue
            break
    if indented_lines:
        try:
            return json.loads("\n".join(indented_lines))
        except Exception:
            return {}

    return {}


def _extract_feature_descriptions(section: str) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    if not section:
        return descriptions

    for line in section.splitlines():
        bullet = re.match(r"^\s*-\s*`?([a-zA-Z0-9_]+)`?\s*[—-]\s*(.+)$", line)
        if bullet:
            descriptions[bullet.group(1)] = _strip_markdown(bullet.group(2))

    rows = [line for line in section.splitlines() if line.strip().startswith("|")]
    for row in rows:
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0] not in {"#", "---", "Feature"} and not cells[0].startswith("---"):
            key = cells[1].strip("` ")
            description = _strip_markdown(cells[2])
            if key and re.fullmatch(r"[a-zA-Z0-9_]+", key):
                descriptions[key] = description

    return descriptions


def _extract_inline_input_shape(text: str) -> tuple[str, str]:
    key_match = re.search(r"input\s*[:\-]\s*([a-zA-Z0-9_]+)", text, flags=re.IGNORECASE)
    shape_match = re.search(r"shape\s*\\?\[\s*1\s*,\s*(\d+)\s*\\?\]", text, flags=re.IGNORECASE)
    return (
        key_match.group(1) if key_match else "features",
        f"[1, {shape_match.group(1)}]" if shape_match else "[1, 1]",
    )


def _extract_inline_output_keys(text: str) -> list[str]:
    normalized = text.replace("\\_", "_")
    match = re.search(r"output\s*[:\-]\s*([a-zA-Z0-9_]+)", normalized, flags=re.IGNORECASE)
    if match:
        return [match.group(1)]
    return []


def _extract_inline_features(text: str) -> dict[str, str]:
    normalized = text.replace("\\_", "_")
    features: dict[str, str] = {}
    for line in normalized.splitlines():
        feature_match = re.match(r"^\s*(?:\\?\[\d+\]|[\[\(]?\d+[\]\)]?)\s*([a-zA-Z0-9_]+)\s+(.+)$", line.strip())
        if feature_match:
            key = feature_match.group(1)
            description = _strip_markdown(feature_match.group(2))
            features[key] = description
    return features


def _extract_inline_sample_input(text: str, feature_descriptions: dict[str, str]) -> dict[str, Any]:
    normalized = text.replace("\\_", "_").replace("\\[", "[").replace("\\]", "]")
    samples = re.findall(r'\{"features":\s*\[\[(.*?)\]\]\}', normalized)
    if not samples:
        return {}

    raw_values = [part.strip() for part in samples[0].split(",")]
    values: list[Any] = []
    for item in raw_values:
        lowered = item.lower()
        if lowered in {"true", "false"}:
            values.append(lowered == "true")
            continue
        try:
            number = float(item)
            if number.is_integer():
                values.append(int(number))
            else:
                values.append(number)
        except Exception:
            values.append(item)

    keys = list(feature_descriptions.keys())
    if not keys:
        keys = [f"feature_{index}" for index in range(len(values))]

    return {key: values[index] for index, key in enumerate(keys[: len(values)])}


def _extract_input_key(text: str) -> str:
    match = re.search(r'model_input\s*=\s*\{\s*"([^"]+)"\s*:', text)
    if match:
        return match.group(1)
    return "features"


def _extract_input_shape(text: str, sample_input: dict[str, Any]) -> str:
    match = re.search(r"shape\s*\[1,\s*(\d+)\]", text, flags=re.IGNORECASE)
    if match:
        return f"[1, {match.group(1)}]"
    return f"[1, {max(len(sample_input), 1)}]"


def _infer_field_kind(value: Any) -> Literal["number", "boolean", "text"]:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    return "text"


def _placeholder_for_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _build_remote_model_definition(payload: dict[str, Any]) -> ModelDefinition:
    description = str(payload.get("description") or "")
    sections = _markdown_sections(description)
    sample_input = _extract_json_object(_section_by_names(sections, "input schema", "sample input"))
    output_schema = _extract_json_object(_section_by_names(sections, "output schema", "sample output"))
    feature_descriptions = _extract_feature_descriptions(_section_by_names(sections, "input features", "input feature"))
    inline_feature_descriptions = _extract_inline_features(description)
    if not feature_descriptions:
        feature_descriptions = inline_feature_descriptions
    if not sample_input:
        sample_input = _extract_inline_sample_input(description, feature_descriptions)
    if not output_schema:
        inline_output_keys = _extract_inline_output_keys(description)
        if inline_output_keys:
            output_schema = {key: None for key in inline_output_keys}

    summary = ""
    for block in re.split(r"\n\s*\n", description):
        cleaned = _strip_markdown(block)
        if cleaned and not cleaned.startswith(payload.get("name", "")):
            summary = cleaned
            break

    input_fields = [
        InputField(
            key=key,
            label=_humanize_key(key),
            kind=_infer_field_kind(value),
            description=feature_descriptions.get(key) or f"Input required by the Hub model for {key}.",
            placeholder=_placeholder_for_value(value),
        )
        for key, value in sample_input.items()
    ]

    what_it_does = summary or f"Runs the Hub model {payload.get('name', 'Custom Model')}."
    what_you_need = [field.description for field in input_fields[:6]] or ["Review the model description and provide the required inputs."]
    result_keys = list(output_schema.keys()) or ["generic_score", "verdict", "summary"]
    what_result_means = [f"{_humanize_key(key)} is part of the model output." for key in result_keys[:4]]
    next_steps = [
        "Fill the inferred input fields from the model description.",
        "Use sample values first if you need to understand the expected format.",
        "Review the output keys to see how this model reports its result.",
    ]

    model_name = str(payload.get("name") or "custom-hub-model")
    author = str(payload.get("authorUsername") or "unknown")
    detected_task_type = str(payload.get("taskName") or "Hub Model")
    input_key, input_shape = _extract_inline_input_shape(description)
    if not sample_input and input_shape == "[1, 1]" and input_fields:
        input_shape = f"[1, {len(input_fields)}]"
    if sample_input and output_schema and input_fields:
        schema_confidence: Literal["high", "medium", "low"] = "high"
    elif sample_input or input_fields or output_schema:
        schema_confidence = "medium"
    else:
        schema_confidence = "low"
    return ModelDefinition(
        slug=_slugify_model_name(model_name),
        title=model_name.replace("-", " "),
        owner=author,
        hub_url=f"https://hub.opengradient.ai/models/{author}/{model_name}",
        model_cid=str(payload.get("llmPath") or "HUB_DYNAMIC"),
        category=detected_task_type,
        summary=summary or f"Custom model resolved from the OpenGradient Hub page for {model_name}.",
        input_key=_extract_input_key(description) if 'model_input' in description else input_key,
        input_shape=_extract_input_shape(description, sample_input) if 'shape [' in description.lower() else input_shape,
        result_keys=result_keys,
        input_fields=input_fields,
        sample_input=sample_input,
        guide=ModelGuide(
            what_it_does=what_it_does,
            what_you_need=what_you_need,
            what_result_means=what_result_means,
            next_steps=next_steps,
        ),
        source="hub_dynamic",
        schema_confidence=schema_confidence,
        detected_task_type=detected_task_type,
    )


def resolve_model(model_ref: str) -> ModelDefinition:
    """Resolve a model URL, slug, or CID into a known registry entry."""
    normalized = model_ref.strip()

    for model in MODEL_REGISTRY.values():
        if normalized == model.model_cid:
            return model
        if normalized.lower() == model.slug.lower():
            return model
        if normalized.rstrip("/") == model.hub_url.rstrip("/"):
            return model
        if re.search(re.escape(model.slug), normalized, flags=re.IGNORECASE):
            return model
        if re.search(re.escape(model.model_cid), normalized):
            return model

    hub_ref = _parse_hub_model_ref(normalized)
    if hub_ref:
        author, name = hub_ref
        try:
            return _fetch_remote_model_definition(author, name)
        except requests.RequestException as exc:
            raise KeyError(f"Custom hub model could not be resolved: {exc}") from exc

    raise KeyError(f"Unknown model reference: {model_ref}")


def supports_live_inference() -> bool:
    return bool(settings.og_enable_live_inference and settings.og_private_key and og is not None)


def supports_live_llm() -> bool:
    return bool(
        settings.og_enable_live_llm
        and settings.og_private_key
        and og is not None
        and hasattr(og, "LLM")
        and hasattr(og, "TEE_LLM")
        and monotonic() >= _llm_cooldown_until
    )


def list_models() -> list[ModelDefinition]:
    return list(MODEL_REGISTRY.values())


def search_models(query: str) -> list[ModelDefinition]:
    normalized = query.strip().lower()
    if not normalized:
        return list_models()

    ranked: list[tuple[int, ModelDefinition]] = []
    for model in MODEL_REGISTRY.values():
        haystack = " ".join(
            [
                model.slug,
                model.title,
                model.category,
                model.summary,
                model.guide.what_it_does,
            ]
        ).lower()
        score = 0
        if normalized in model.slug.lower():
            score += 5
        if normalized in model.title.lower():
            score += 4
        if normalized in model.category.lower():
            score += 3
        if normalized in model.summary.lower():
            score += 2
        if normalized in model.guide.what_it_does.lower():
            score += 1
        if score:
            ranked.append((score, model))

    ranked.sort(key=lambda item: (-item[0], item[1].title))
    return [model for _, model in ranked]


def fetch_protocol_preview(url: str) -> dict[str, Any]:
    normalized = _normalize_protocol_url(url)
    parsed = urlparse(normalized)
    host = parsed.netloc

    try:
        response = requests.get(
            normalized,
            timeout=8,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
                )
            },
        )
        html = response.text[:250000]
        headers = response.headers
    except Exception:
        return {
            "url": normalized,
            "host": host,
            "title": None,
            "description": None,
            "image_url": None,
            "site_name": None,
            "embed_allowed": False,
            "status_code": None,
        }

    return {
        "url": normalized,
        "host": host,
        "title": _extract_html_title(html),
        "description": _extract_meta_content(html, "description")
        or _extract_meta_content(html, "og:description")
        or _extract_meta_content(html, "twitter:description"),
        "image_url": _resolve_meta_url(
            normalized,
            _extract_meta_content(html, "og:image") or _extract_meta_content(html, "twitter:image"),
        ),
        "site_name": _extract_meta_content(html, "og:site_name"),
        "embed_allowed": _is_embed_allowed(headers),
        "status_code": response.status_code,
    }


def build_protocol_proxy_html(url: str) -> str:
    normalized = _normalize_protocol_url(url)

    try:
        response = requests.get(
            normalized,
            timeout=12,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
                )
            },
        )
        response.raise_for_status()
        html = response.text
    except Exception as exc:
        return _protocol_error_html(normalized, f"Protocol preview could not be loaded: {exc}")

    proxied = _prepare_proxied_html(normalized, html)
    return proxied or _protocol_error_html(normalized, "Protocol preview returned an empty document.")


def _get_alpha_client():
    return og.Alpha(
        private_key=settings.og_private_key,
        rpc_url=settings.og_rpc_url,
        api_url=settings.og_api_url,
        inference_contract_address=settings.og_inference_contract_address,
    )


def _get_llm_client():
    return og.LLM(
        private_key=settings.og_private_key,
        rpc_url=settings.og_rpc_url,
    )


def _get_tee_llm_model():
    preferred = settings.og_tee_llm_model.strip().upper()
    if hasattr(og.TEE_LLM, preferred):
        return getattr(og.TEE_LLM, preferred)
    return og.TEE_LLM.GPT_5_MINI


def list_available_llm_models() -> list[str]:
    if og is None or not hasattr(og, "TEE_LLM"):
        return []
    return sorted(name for name in dir(og.TEE_LLM) if name.isupper())


def resolve_tee_llm_model_name(preferred: str | None = None) -> str:
    available = list_available_llm_models()
    candidate = (preferred or settings.og_tee_llm_model).strip().upper()
    if candidate in available:
        return candidate
    return "GPT_5_MINI" if "GPT_5_MINI" in available else (available[0] if available else candidate)


def _get_tee_llm_model_by_name(preferred: str | None = None):
    resolved = resolve_tee_llm_model_name(preferred)
    if hasattr(og.TEE_LLM, resolved):
        return getattr(og.TEE_LLM, resolved)
    return _get_tee_llm_model()


def _extract_llm_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    content = getattr(response, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(response, dict):
        for key in ("text", "content", "message"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return str(response).strip()


def _normalize_protocol_url(url: str) -> str:
    raw = url.strip()
    if not raw:
        return raw
    if raw.startswith(("http://", "https://")):
        return raw
    return f"https://{raw}"


def _extract_html_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _clean_meta_text(match.group(1))


def _extract_meta_content(html: str, key: str) -> str | None:
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(key)}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']{re.escape(key)}["\']',
        rf'<meta[^>]+name=["\']{re.escape(key)}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']{re.escape(key)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return _clean_meta_text(match.group(1))
    return None


def _clean_meta_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", unescape(value)).strip()
    return cleaned or None


def _resolve_meta_url(base_url: str, maybe_url: str | None) -> str | None:
    if not maybe_url:
        return None
    return urljoin(base_url, maybe_url)


def _is_embed_allowed(headers: requests.structures.CaseInsensitiveDict[str]) -> bool:
    x_frame_options = headers.get("x-frame-options", "").lower()
    if "deny" in x_frame_options or "sameorigin" in x_frame_options:
        return False

    csp = headers.get("content-security-policy", "").lower()
    if "frame-ancestors" not in csp:
        return True

    match = re.search(r"frame-ancestors\s+([^;]+)", csp)
    if not match:
        return True

    policy = match.group(1)
    if "*" in policy:
        return True
    if "'self'" in policy or "none" in policy:
        return False
    return True


def _prepare_proxied_html(base_url: str, html: str) -> str:
    document = html or ""

    # Remove meta CSP or frame guards that can interfere with embedded rendering in the local runner shell.
    document = re.sub(
        r"<meta[^>]+http-equiv=[\"']Content-Security-Policy[\"'][^>]*>",
        "",
        document,
        flags=re.IGNORECASE,
    )
    document = re.sub(
        r"<meta[^>]+http-equiv=[\"']X-Frame-Options[\"'][^>]*>",
        "",
        document,
        flags=re.IGNORECASE,
    )

    # Keep a safe static render inside the runner viewport instead of executing third-party app code under the local origin.
    document = re.sub(
        r"<script\b[^>]*>.*?</script>",
        "",
        document,
        flags=re.IGNORECASE | re.DOTALL,
    )
    document = re.sub(
        r"<script\b[^>]*/>",
        "",
        document,
        flags=re.IGNORECASE | re.DOTALL,
    )

    base_tag = f'<base href="{base_url}">'
    style_tag = """
<style>
html, body {
  min-height: 100%;
  background: #0b1320 !important;
}
body {
  margin: 0 !important;
}
</style>
""".strip()

    if re.search(r"<head[^>]*>", document, flags=re.IGNORECASE):
        document = re.sub(
            r"(<head[^>]*>)",
            r"\1" + base_tag + style_tag,
            document,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        document = f"<head>{base_tag}{style_tag}</head>{document}"

    return document


def _protocol_error_html(url: str, message: str) -> str:
    host = urlparse(url).netloc or url
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{host}</title>
    <style>
      :root {{
        color-scheme: dark;
      }}
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: radial-gradient(circle at top, rgba(36,188,227,0.14), transparent 28%), #0b1320;
        color: #d7e5f7;
        font: 16px/1.5 "IBM Plex Sans", "Segoe UI", sans-serif;
      }}
      .card {{
        width: min(38rem, calc(100% - 2rem));
        border-radius: 1rem;
        border: 1px solid rgba(206,229,249,0.12);
        background: rgba(15,24,40,0.88);
        padding: 1rem 1.1rem;
      }}
      .host {{
        margin: 0 0 0.4rem;
        font-size: 0.72rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #8eb6d7;
      }}
      .copy {{
        margin: 0;
        color: rgba(215,229,247,0.82);
      }}
    </style>
  </head>
  <body>
    <div class="card">
      <p class="host">{host}</p>
      <p class="copy">{message}</p>
    </div>
  </body>
</html>"""


def _await_llm_response(value: Any) -> Any:
    if not asyncio.iscoroutine(value):
        return value

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(value)

    result_box: dict[str, Any] = {}
    error_box: dict[str, BaseException] = {}

    def runner():
        try:
            result_box["value"] = asyncio.run(value)
        except BaseException as exc:  # pragma: no cover
            error_box["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()

    if "error" in error_box:
        raise error_box["error"]
    return result_box.get("value")


def build_bridge_leaderboard() -> list[LeaderboardEntry]:
    model = MODEL_REGISTRY["cross-chain-bridge-risk-classifier"]
    entries: list[LeaderboardEntry] = []

    for profile in BRIDGE_LEADERBOARD_PROFILES:
        normalized_input = {**model.sample_input, **profile["overrides"]}
        result = _shape_bridge_result({}, normalized_input)
        entries.append(
            LeaderboardEntry(
                rank=0,
                source="curated",
                model_slug=model.slug,
                model_title=model.title,
                model_category=model.category,
                name=profile["name"],
                protocol_url=profile["protocol_url"],
                summary=profile["summary"],
                created_at=None,
                headline_score=str(result.get("risk_score", "-")),
                headline_label=str(result.get("risk_category", "-")),
                normalized_input=normalized_input,
                result=result,
            )
        )

    for user_entry in _load_model_runs(model_slug=model.slug):
        entries.append(user_entry)

    entries.sort(
        key=lambda entry: (
            float(entry.result.get("risk_score") or 0),
            float(entry.normalized_input.get("prior_incidents") or 0),
            entry.created_at or "",
        )
    )

    for index, entry in enumerate(entries, start=1):
        entry.rank = index

    return entries


def build_global_leaderboard(limit: int = 8) -> list[LeaderboardEntry]:
    entries = _load_model_runs()
    entries.sort(
        key=lambda entry: (
            entry.created_at or "",
            entry.rank,
        ),
        reverse=True,
    )

    deduped_entries: list[LeaderboardEntry] = []
    seen_keys: set[tuple[str, str]] = set()
    for entry in entries:
        key = _global_leaderboard_key(entry)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped_entries.append(entry)
        if len(deduped_entries) >= limit:
            break

    for index, entry in enumerate(deduped_entries, start=1):
        entry.rank = index

    return deduped_entries


def build_model_usage(limit: int = 5) -> list[ModelUsageStat]:
    counters: dict[str, ModelUsageStat] = {}
    for entry in _load_model_runs():
        if not entry.model_slug or not entry.model_title:
            continue
        if entry.model_slug not in counters:
            counters[entry.model_slug] = ModelUsageStat(
                model_slug=entry.model_slug,
                model_title=entry.model_title,
                runs=0,
            )
        counters[entry.model_slug].runs += 1

    return sorted(counters.values(), key=lambda item: item.runs, reverse=True)[:limit]


def _global_leaderboard_key(entry: LeaderboardEntry) -> tuple[str, str]:
    model_key = (entry.model_slug or entry.model_title or "unknown-model").strip().lower()
    protocol_key = _normalize_leaderboard_protocol_url(entry.protocol_url)
    return model_key, protocol_key


def _normalize_leaderboard_protocol_url(url: str | None) -> str:
    if not url:
        return "unknown-url"

    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/").lower() or "/"
    return f"{host}{path}"


def save_model_run(
    *,
    model: ModelDefinition,
    normalized_input: dict[str, Any],
    result: dict[str, Any],
    target_url: str | None,
    compare_url: str | None = None,
) -> LeaderboardEntry:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    current_entries = _read_model_run_records()

    host = getHostLabel(target_url or "") if target_url else None
    fallback_name = f"User run {len(current_entries) + 1}"
    created_at = datetime.now(UTC).isoformat()
    protocol_url = target_url or compare_url or "https://hub.opengradient.ai"
    headline_score, headline_label = _headline_for_model(model, result)
    summary = _build_user_run_summary(model, normalized_input, result, compare_url=compare_url)

    record = {
        "rank": 0,
        "source": "user",
        "model_slug": model.slug,
        "model_title": model.title,
        "model_category": model.category,
        "name": host or fallback_name,
        "protocol_url": protocol_url,
        "summary": summary,
        "created_at": created_at,
        "headline_score": headline_score,
        "headline_label": headline_label,
        "normalized_input": normalized_input,
        "result": result,
    }
    current_entries.append(record)
    MODEL_RUNS_PATH.write_text(json.dumps(current_entries, indent=2), encoding="utf-8")

    return LeaderboardEntry(**record)


def _load_model_runs(model_slug: str | None = None) -> list[LeaderboardEntry]:
    records = _read_model_run_records()
    entries: list[LeaderboardEntry] = []
    for record in records:
        try:
            normalized_record = _normalize_legacy_run_record(record)
            entry = LeaderboardEntry(**normalized_record)
            if model_slug and entry.model_slug != model_slug:
                continue
            entries.append(entry)
        except Exception:
            continue
    return entries


def _read_model_run_records() -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    for path in (MODEL_RUNS_PATH, BRIDGE_RUNS_PATH):
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, list):
            combined.extend(item for item in payload if isinstance(item, dict))
    return combined


def _build_user_run_summary(
    model: ModelDefinition,
    normalized_input: dict[str, Any],
    result: dict[str, Any],
    *,
    compare_url: str | None,
) -> str:
    compare_note = " Includes side-by-side compare run." if compare_url else ""
    if model.slug == "cross-chain-bridge-risk-classifier":
        audits = normalized_input.get("num_audits", "-")
        timelock = normalized_input.get("time_lock_hours", "-")
        incidents = normalized_input.get("prior_incidents", "-")
        category = result.get("risk_category", "UNKNOWN")
        return (
            f"Saved user bridge run with {category} risk, {audits} audits, "
            f"{timelock}h timelock, and {incidents} incident markers.{compare_note}"
        )

    headline_score, headline_label = _headline_for_model(model, result)
    return f"Saved user run for {model.title} with score {headline_score} and label {headline_label}.{compare_note}"


def _headline_for_model(model: ModelDefinition, result: dict[str, Any]) -> tuple[str, str]:
    if model.slug == "governance-capture-risk-scorer":
        return str(result.get("governance_capture_risk_score", "-")), f"Grade {result.get('grade', '-')}"
    if model.slug == "cross-chain-bridge-risk-classifier":
        return str(result.get("risk_score", "-")), str(result.get("risk_category", "-"))
    if model.slug == "defi-protocol-health-score":
        return str(result.get("health_score", "-")), f"Grade {result.get('grade', '-')}"
    if model.slug == "dex-liquidity-exit-risk-scorer":
        return str(result.get("liquidity_exit_risk_score", "-")), str(result.get("risk_level", "-"))
    if model.slug == "stablecoin-depeg-risk-monitor":
        return str(result.get("depeg_risk_score", "-")), str(result.get("alert", "-"))
    return str(result.get("wash_probability", "-")), str(result.get("verdict", "-"))


def _normalize_legacy_run_record(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("model_slug") and record.get("model_title"):
        return record

    result = record.get("result") or {}
    inferred_model = _infer_model_from_result(result)
    if inferred_model is None:
        return record

    headline_score, headline_label = _headline_for_model(inferred_model, result)
    normalized = dict(record)

    if not normalized.get("model_slug"):
        normalized["model_slug"] = inferred_model.slug
    if not normalized.get("model_title"):
        normalized["model_title"] = inferred_model.title
    if not normalized.get("model_category"):
        normalized["model_category"] = inferred_model.category
    if not normalized.get("headline_score"):
        normalized["headline_score"] = headline_score
    if not normalized.get("headline_label"):
        normalized["headline_label"] = headline_label

    return normalized


def _infer_model_from_result(result: dict[str, Any]) -> ModelDefinition | None:
    if "governance_capture_risk_score" in result:
        return MODEL_REGISTRY["governance-capture-risk-scorer"]
    if "risk_score" in result and "risk_category" in result:
        return MODEL_REGISTRY["cross-chain-bridge-risk-classifier"]
    if "health_score" in result:
        return MODEL_REGISTRY["defi-protocol-health-score"]
    if "liquidity_exit_risk_score" in result:
        return MODEL_REGISTRY["dex-liquidity-exit-risk-scorer"]
    if "depeg_risk_score" in result:
        return MODEL_REGISTRY["stablecoin-depeg-risk-monitor"]
    if "wash_probability" in result:
        return MODEL_REGISTRY["nft-wash-trading-detector"]
    return None


def _grade_from_score(score: float) -> str:
    if score <= 20:
        return "A"
    if score <= 40:
        return "B"
    if score <= 60:
        return "C"
    if score <= 80:
        return "D"
    return "F"


def _bridge_category(score: float) -> tuple[int, str]:
    if score <= 25:
        return 0, "LOW"
    if score <= 50:
        return 1, "MEDIUM"
    if score <= 75:
        return 2, "HIGH"
    return 3, "CRITICAL"


def _scalarize(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        if value.size == 1:
            return value.item()
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, dict):
        return {key: _scalarize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scalarize(item) for item in value]
    return value


def _governance_vector(values: dict[str, Any]) -> list[float]:
    order = [
        "top1_holder_share",
        "top5_holder_share",
        "top10_holder_share",
        "gini_voting_power",
        "insider_voting_share",
        "active_delegate_share",
        "circulating_vote_ratio",
        "multisig_signer_concentration",
        "multisig_threshold_risk",
        "upgrade_timelock_risk",
        "admin_key_centralization",
        "emergency_pause_abuse_risk",
        "signer_overlap_risk",
        "treasury_execution_centralization",
        "guardian_override_risk",
        "proposal_quorum_fragility",
        "delegate_absenteeism",
        "voter_participation_decay",
        "flashloan_vote_exposure",
        "proposal_turnout_volatility",
        "proposal_cancel_risk",
        "voting_window_fragility",
        "proposal_latency_risk",
        "borrowable_supply_share",
        "dex_liquidity_concentration",
        "slippage_1m_buy_risk",
        "whale_inflow_spike",
        "unlock_overhang_risk",
        "lending_concentration_risk",
        "governance_volume_spike",
    ]
    return [float(values[key]) for key in order]


def _bridge_vector(values: dict[str, Any]) -> list[float]:
    order = [
        "tvl_usd",
        "bridge_age_days",
        "num_audits",
        "audit_score",
        "multisig_threshold",
        "num_signers",
        "admin_key_centralization",
        "time_lock_hours",
        "chains_supported",
        "daily_tx_volume",
        "liquidity_concentration",
        "prior_incidents",
        "incident_severity_max",
        "bug_bounty_usd",
        "uses_light_client",
        "uses_zk_proof",
        "validator_set_size",
        "code_open_source",
    ]
    return [float(values[key]) for key in order]


def _protocol_health_vector(values: dict[str, Any]) -> list[float]:
    order = [
        "tvl_usd",
        "tvl_7d_change",
        "tvl_30d_change",
        "tvl_30d_volatility",
        "tvl_top3_pool_concentration",
        "tvl_vs_sector_median",
        "days_since_deploy",
        "audit_count",
        "auditor_tier",
        "has_bug_bounty",
        "bug_bounty_max_payout_usd",
        "is_upgradeable",
        "timelock_hours",
        "exploit_history_count",
        "exploit_total_loss_usd",
        "governance_token_gini",
        "top10_holder_share",
        "multisig_threshold",
        "unique_governance_voters_30d",
        "dao_proposals_90d",
        "founding_team_token_share",
        "volume_to_tvl_ratio_7d",
        "unique_users_30d",
        "user_growth_rate_30d",
        "token_liquidity_depth_usd",
        "revenue_30d_usd",
        "revenue_to_tvl_ratio",
        "treasury_usd",
        "treasury_runway_months",
        "native_token_share_of_treasury",
        "stablecoin_share_of_treasury",
        "revenue_covers_opex",
    ]
    return [float(values[key]) for key in order]


def _stablecoin_vector(values: dict[str, Any]) -> list[float]:
    order = [
        "collateral_ratio",
        "reserve_change_7d",
        "peg_token_share",
        "treasury_runway_days",
        "mint_redeem_ratio_7d",
        "peg_deviation_pct",
        "peg_deviation_7d_max",
        "dex_volume_7d_change",
        "funding_rate_perps",
        "cex_volume_7d_change",
        "dex_liquidity_usd",
        "pool_concentration",
        "slippage_1m_usd",
        "liquidity_7d_change",
        "redemption_queue_usd",
        "transfer_volume_7d_change",
        "unique_senders_7d_change",
        "whale_outflow_7d",
        "bridge_outflow_7d",
        "smart_contract_net_flow",
    ]
    return [float(values[key]) for key in order]


def _dex_liquidity_exit_vector(values: dict[str, Any]) -> list[float]:
    order = [
        "pool_tvl_usd",
        "liquidity_7d_change",
        "liquidity_30d_change",
        "lp_top10_share",
        "treasury_lp_share",
        "protocol_owned_liquidity_share",
        "incentive_apr",
        "fee_apr",
        "emissions_30d_usd",
        "emissions_to_fees_ratio",
        "volume_tvl_ratio_7d",
        "slippage_100k_buy_pct",
        "slippage_100k_sell_pct",
        "bridge_dependent_liquidity_share",
        "whale_lp_exit_7d",
        "net_swap_flow_7d",
        "unique_lp_count",
        "top_pool_share_of_protocol",
        "token_unlock_30d_usd",
        "governance_timelock_hours",
        "audit_count",
        "exploit_history_count",
        "oracle_dependency_score",
        "correlated_asset_risk",
    ]
    return [float(values[key]) for key in order]


def _nft_vector(values: dict[str, Any]) -> list[float]:
    order = [
        "price_eth",
        "time_delta_sec",
        "buyer_tx_count",
        "seller_tx_count",
        "wallet_overlap_score",
        "gas_paid_gwei",
    ]
    return [float(values[key]) for key in order]


def _build_live_model_input(model: ModelDefinition, values: dict[str, Any]) -> dict[str, Any]:
    if model.slug == "governance-capture-risk-scorer":
        return {model.input_key: [_governance_vector(values)]}
    if model.slug == "cross-chain-bridge-risk-classifier":
        return {model.input_key: [_bridge_vector(values)]}
    if model.slug == "dex-liquidity-exit-risk-scorer":
        return {model.input_key: [_dex_liquidity_exit_vector(values)]}
    if model.slug == "stablecoin-depeg-risk-monitor":
        return {model.input_key: [_stablecoin_vector(values)]}
    if model.slug == "nft-wash-trading-detector":
        return {model.input_key: [_nft_vector(values)]}
    return {model.input_key: [_protocol_health_vector(values)]}


def infer_inputs_from_url(model: ModelDefinition, target_url: str | None) -> tuple[dict[str, Any], list[str]]:
    """Heuristic URL-to-feature mapping for the first OG Runner experience."""
    if not target_url:
        return {}, []

    parsed = urlparse(target_url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    combined = f"{host}{path}"
    page_context = combined
    warnings = [
        "URL mode is heuristic right now. Review the generated inputs before trusting the result."
    ]

    try:
        response = requests.get(target_url, timeout=4, headers={"User-Agent": "OG-Runner/0.1"})
        if response.ok and response.text:
            title_match = re.search(r"<title>(.*?)</title>", response.text, flags=re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip().lower() if title_match else ""
            body_text = re.sub(r"<[^>]+>", " ", response.text[:20000]).lower()
            page_context = f"{combined} {title} {body_text}"
        else:
            warnings.append("Target URL did not return a readable page. Using domain-level inference only.")
    except Exception:
        warnings.append("Target URL could not be fetched. Using domain-level inference only.")

    if model.slug == "governance-capture-risk-scorer":
        governance_aliases: list[str] = []
        governance_coin_id: str | None = None
        if "aave" in page_context:
            governance_aliases = ["aave"]
            governance_coin_id = "aave"
            base = {
                "top1_holder_share": 0.11,
                "top10_holder_share": 0.46,
                "insider_voting_share": 0.16,
                "proposal_quorum_fragility": 0.29,
                "flashloan_vote_exposure": 0.08,
                "borrowable_supply_share": 0.14,
            }
        elif "compound" in page_context:
            governance_aliases = ["compound", "compound governance"]
            governance_coin_id = "compound-governance-token"
            base = {
                "top1_holder_share": 0.14,
                "top10_holder_share": 0.58,
                "insider_voting_share": 0.24,
                "proposal_quorum_fragility": 0.41,
                "flashloan_vote_exposure": 0.10,
                "borrowable_supply_share": 0.19,
            }
        elif "maker" in page_context or "sky.money" in page_context or "makerdao" in page_context:
            governance_aliases = ["makerdao", "maker", "sky"]
            governance_coin_id = "maker"
            base = {
                "top1_holder_share": 0.09,
                "top10_holder_share": 0.43,
                "insider_voting_share": 0.18,
                "proposal_quorum_fragility": 0.27,
                "flashloan_vote_exposure": 0.06,
                "borrowable_supply_share": 0.09,
            }
        else:
            base = {
            "proposal_quorum_fragility": 0.38,
            "borrowable_supply_share": 0.17,
            }

        live_protocol = _fetch_llama_protocol(host or page_context, governance_aliases)
        if live_protocol:
            tvl = float(live_protocol.get("tvl") or 0)
            if tvl > 0:
                base["proposal_quorum_fragility"] = round(max(0.15, min(0.65, 0.45 - min(tvl / 5_000_000_000, 0.25))), 3)
                base["borrowable_supply_share"] = round(max(0.05, min(0.30, base["borrowable_supply_share"] + (0.08 if tvl < 250_000_000 else -0.02))), 3)
            warnings.append(
                f"Live protocol snapshot applied from DeFiLlama for {live_protocol.get('name', 'protocol')}."
            )

        if governance_coin_id:
            live_market = _fetch_coingecko_simple_price(governance_coin_id)
            if live_market:
                market_cap = float(live_market.get("usd_market_cap") or 0)
                day_volume = float(live_market.get("usd_24h_vol") or 0)
                day_change = abs(float(live_market.get("usd_24h_change") or 0)) / 100
                if market_cap > 0:
                    volume_to_mcap = min(day_volume / market_cap, 1.0)
                    base["borrowable_supply_share"] = round(max(0.04, min(0.35, volume_to_mcap * 0.9)), 3)
                    base["governance_volume_spike"] = round(min(1.0, volume_to_mcap * 2.5), 3)
                    base["whale_inflow_spike"] = round(min(1.0, day_change * 2.2), 3)
                    base["flashloan_vote_exposure"] = round(min(0.5, max(base["flashloan_vote_exposure"], volume_to_mcap * 0.45)), 3)
                warnings.append(f"Live token market snapshot applied from CoinGecko for {governance_coin_id}.")
            else:
                warnings.append("Live token market snapshot was unavailable; governance URL mode used static defaults.")

        return base, warnings

    if model.slug == "cross-chain-bridge-risk-classifier":
        if "wormhole" in page_context:
            base = {
                "tvl_usd": 800000000,
                "num_audits": 3,
                "multisig_threshold": 0.67,
                "time_lock_hours": 0,
                "prior_incidents": 1,
                "uses_zk_proof": 0,
            }
        elif "stargate" in page_context:
            base = {
                "tvl_usd": 500000000,
                "num_audits": 4,
                "multisig_threshold": 0.75,
                "time_lock_hours": 48,
                "prior_incidents": 0,
                "uses_zk_proof": 0,
            }
        elif "polygon" in page_context or "bridge" in page_context:
            base = {
                "tvl_usd": 650000000,
                "num_audits": 4,
                "multisig_threshold": 0.6,
                "time_lock_hours": 24,
                "prior_incidents": 0,
                "uses_zk_proof": 0,
            }
        else:
            base = {
            "multisig_threshold": 0.62,
            "time_lock_hours": 24,
            }

        bridge_aliases = []
        if "wormhole" in page_context:
            bridge_aliases = ["wormhole", "portal", "portalbridge", "portal bridge"]
        elif "stargate" in page_context:
            bridge_aliases = ["stargate", "stargate v2", "stargate finance"]
        elif "polygon" in page_context:
            bridge_aliases = ["polygon bridge", "polygon zkevm bridge", "polygon"]

        live_bridge = _fetch_llama_protocol(host or page_context, bridge_aliases)
        if live_bridge:
            if live_bridge.get("tvl") is not None:
                base["tvl_usd"] = float(live_bridge["tvl"])
            chains = live_bridge.get("chains") or []
            if isinstance(chains, list) and chains:
                base["chains_supported"] = len(chains)
            if base.get("daily_tx_volume") is None and base.get("tvl_usd") is not None:
                base["daily_tx_volume"] = round(float(base["tvl_usd"]) * 0.02)
            warnings.append(
                f"Live protocol snapshot applied from DeFiLlama for {live_bridge.get('name', 'bridge protocol')}."
            )
        else:
            warnings.append("Live bridge protocol snapshot was unavailable; bridge URL mode used profile defaults.")

        return base, warnings

    if model.slug == "dex-liquidity-exit-risk-scorer":
        dex_aliases: list[str] = []
        if "uniswap" in page_context:
            dex_aliases = ["uniswap", "uniswap v3", "uniswap v4"]
            base = {
                "pool_tvl_usd": 420000000,
                "liquidity_7d_change": -0.02,
                "lp_top10_share": 0.46,
                "slippage_100k_buy_pct": 0.007,
                "emissions_to_fees_ratio": 0.18,
                "whale_lp_exit_7d": 0.03,
            }
        elif "aerodrome" in page_context:
            dex_aliases = ["aerodrome", "aerodrome finance"]
            base = {
                "pool_tvl_usd": 180000000,
                "liquidity_7d_change": -0.07,
                "lp_top10_share": 0.59,
                "slippage_100k_buy_pct": 0.014,
                "emissions_to_fees_ratio": 1.2,
                "whale_lp_exit_7d": 0.08,
            }
        elif "curve" in page_context:
            dex_aliases = ["curve", "curve finance"]
            base = {
                "pool_tvl_usd": 360000000,
                "liquidity_7d_change": -0.05,
                "lp_top10_share": 0.54,
                "slippage_100k_buy_pct": 0.006,
                "emissions_to_fees_ratio": 0.72,
                "whale_lp_exit_7d": 0.05,
            }
        elif "sushi" in page_context:
            dex_aliases = ["sushiswap", "sushi"]
            base = {
                "pool_tvl_usd": 95000000,
                "liquidity_7d_change": -0.09,
                "lp_top10_share": 0.63,
                "slippage_100k_buy_pct": 0.018,
                "emissions_to_fees_ratio": 1.45,
                "whale_lp_exit_7d": 0.11,
            }
        else:
            base = {
                "pool_tvl_usd": 140000000,
                "liquidity_7d_change": -0.06,
                "lp_top10_share": 0.57,
                "slippage_100k_buy_pct": 0.013,
                "emissions_to_fees_ratio": 1.0,
                "whale_lp_exit_7d": 0.07,
            }

        live_dex = _fetch_llama_protocol(host or page_context, dex_aliases)
        if live_dex:
            if live_dex.get("tvl") is not None:
                base["pool_tvl_usd"] = float(live_dex["tvl"])
            if live_dex.get("change_7d") is not None:
                base["liquidity_7d_change"] = float(live_dex["change_7d"]) / 100
            warnings.append(
                f"Live protocol snapshot applied from DeFiLlama for {live_dex.get('name', 'dex protocol')}."
            )
        else:
            warnings.append("Live DEX snapshot was unavailable; URL mode used profile defaults.")

        return base, warnings

    if model.slug == "stablecoin-depeg-risk-monitor":
        live_snapshot = None
        live_coin_id = None
        if "maker" in page_context or "dai" in page_context:
            live_coin_id = "dai"
            base = {
                "collateral_ratio": 1.55,
                "reserve_change_7d": -0.01,
                "peg_deviation_pct": 0.001,
                "dex_liquidity_usd": 120000000,
                "whale_outflow_7d": 0.01,
                "transfer_volume_7d_change": 0.05,
            }
        elif "frax" in page_context:
            live_coin_id = "frax"
            base = {
                "collateral_ratio": 1.08,
                "reserve_change_7d": -0.06,
                "peg_deviation_pct": 0.004,
                "dex_liquidity_usd": 45000000,
                "whale_outflow_7d": 0.04,
                "transfer_volume_7d_change": 0.17,
            }
        elif "usdc" in page_context or "usd coin" in page_context:
            live_coin_id = "usd-coin"
            base = {
                "collateral_ratio": 1.00,
                "reserve_change_7d": 0.0,
                "peg_deviation_pct": 0.001,
                "dex_liquidity_usd": 160000000,
                "whale_outflow_7d": 0.01,
                "transfer_volume_7d_change": 0.04,
            }
        elif "usdt" in page_context or "tether" in page_context:
            live_coin_id = "tether"
            base = {
                "collateral_ratio": 1.00,
                "reserve_change_7d": 0.0,
                "peg_deviation_pct": 0.001,
                "dex_liquidity_usd": 190000000,
                "whale_outflow_7d": 0.01,
                "transfer_volume_7d_change": 0.05,
            }
        elif "ust" in page_context or "terra" in page_context:
            base = {
                "collateral_ratio": 0.92,
                "reserve_change_7d": -0.35,
                "peg_deviation_pct": 0.06,
                "dex_liquidity_usd": 7000000,
                "whale_outflow_7d": 0.22,
                "transfer_volume_7d_change": 2.4,
            }
        else:
            base = {
            "collateral_ratio": 1.1,
            "peg_deviation_pct": 0.003,
            }

        if live_coin_id:
            live_snapshot = _fetch_coingecko_simple_price(live_coin_id)
            if live_snapshot and "usd" in live_snapshot:
                price = float(live_snapshot["usd"])
                day_change = abs(float(live_snapshot.get("usd_24h_change") or 0.0)) / 100
                base["peg_deviation_pct"] = round(abs(1 - price), 6)
                base["peg_deviation_7d_max"] = max(base.get("peg_deviation_7d_max", 0.0), round(abs(1 - price) * 2.2, 6))
                base["dex_volume_7d_change"] = max(base.get("dex_volume_7d_change", 0.0), round(day_change * 1.8, 4))
                base["cex_volume_7d_change"] = max(base.get("cex_volume_7d_change", 0.0), round(day_change * 1.2, 4))
                warnings.append(f"Live market snapshot applied from CoinGecko for {live_coin_id}.")
            else:
                warnings.append("Live market snapshot was unavailable; stablecoin URL mode used static defaults.")

        return base, warnings

    return {}, warnings


def _fetch_coingecko_simple_price(coin_id: str) -> dict[str, Any] | None:
    """Fetch a small live price snapshot for a known coin id."""
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": coin_id,
                "vs_currencies": "usd",
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true",
            },
            timeout=4,
            headers={"User-Agent": "OG-Runner/0.1"},
        )
        if not response.ok:
            return None
        payload = response.json()
        if coin_id not in payload:
            return None
        return payload[coin_id]
    except Exception:
        return None


def getHostLabel(url: str) -> str:
    try:
        normalized = url if url.startswith(("http://", "https://")) else f"https://{url}"
        return urlparse(normalized).netloc.replace("www.", "")
    except Exception:
        return ""


def _fetch_llama_protocol(query: str, aliases: list[str] | None = None) -> dict[str, Any] | None:
    """Fetch a matching DeFiLlama protocol entry for live bridge or protocol hints."""
    try:
        response = requests.get(
            "https://api.llama.fi/protocols",
            timeout=6,
            headers={"User-Agent": "OG-Runner/0.1"},
        )
        if not response.ok:
            return None
        protocols = response.json()
        lowered = query.lower()
        query_host = urlparse(query if query.startswith("http") else f"https://{query}").netloc.lower()

        alias_list = [lowered]
        if aliases:
            alias_list.extend(alias.lower() for alias in aliases)
        if "wormhole" in lowered:
            alias_list.extend(["portal", "portalbridge", "portal bridge"])
        if "polygon" in lowered and "bridge" in lowered:
            alias_list.extend(["polygon zkevm bridge", "polygon bridge"])

        bridge_categories = {"Bridge", "Cross Chain Bridge", "Canonical Bridge", "Chain"}
        matches: list[tuple[int, dict[str, Any]]] = []
        for protocol in protocols:
            name = str(protocol.get("name", "")).lower()
            slug = str(protocol.get("slug", "")).lower()
            url = str(protocol.get("url", "")).lower()
            protocol_host = urlparse(url).netloc.lower() if url else ""
            description = str(protocol.get("description", "")).lower()
            haystack = f"{name} {slug} {url} {description}"

            score = 0
            if query_host and protocol_host:
                if query_host == protocol_host:
                    score += 20
                elif query_host.endswith(protocol_host) or protocol_host.endswith(query_host):
                    score += 14
                elif any(part and part in protocol_host for part in query_host.split(".")):
                    score += 6
            for alias in alias_list:
                if not alias:
                    continue
                if alias == name or alias == slug:
                    score += 12
                elif alias in url:
                    score += 10
                elif alias in name or alias in slug:
                    score += 8
                elif alias in haystack:
                    score += 4
            if protocol.get("category") in bridge_categories:
                score += 3
            if score > 0:
                matches.append((score, protocol))

        if not matches:
            return None

        matches.sort(
            key=lambda item: (
                item[0],
                float(item[1].get("tvl") or 0),
            ),
            reverse=True,
        )
        return matches[0][1]
    except Exception:
        return None


def _governance_flags(values: dict[str, Any]) -> list[str]:
    flags = []
    if float(values["top1_holder_share"]) > 0.15:
        flags.append("TOP_HOLDER_DOMINANCE")
    if float(values["top10_holder_share"]) > 0.60:
        flags.append("OLIGARCHIC_GOVERNANCE")
    if float(values["insider_voting_share"]) > 0.35:
        flags.append("INSIDER_CONTROL")
    if float(values["proposal_quorum_fragility"]) > 0.50:
        flags.append("QUORUM_FRAGILITY")
    if float(values["flashloan_vote_exposure"]) > 0.30:
        flags.append("FLASHLOAN_EXPOSURE")
    if float(values["borrowable_supply_share"]) > 0.25:
        flags.append("BORROWABLE_ATTACK_SURFACE")
    return flags or ["NO_MAJOR_TRIGGER"]


def _shape_governance_result(model_output: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    raw_pressure = model_output.get("governance_capture_pressure")
    if raw_pressure is None:
        raw_pressure = max(sum(_governance_vector(values)), 0.0)

    if isinstance(raw_pressure, list):
        raw_pressure = raw_pressure[0]

    score = min(100.0, round(float(raw_pressure) * 3.33, 1))
    return {
        "governance_capture_pressure": round(float(raw_pressure), 2),
        "governance_capture_risk_score": score,
        "grade": _grade_from_score(score),
        "flags": _governance_flags(values),
    }


def _shape_bridge_result(model_output: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    raw_score = model_output.get("risk_score")
    if raw_score is None:
        raw_score = (
            min(float(values["tvl_usd"]) / 1_000_000_000, 1.0) * 18
            + (1 - float(values["multisig_threshold"])) * 26
            + max(0, 1 - min(float(values["time_lock_hours"]) / 72, 1)) * 18
            + min(float(values["prior_incidents"]) / 3, 1) * 22
            + (1 - min(float(values["num_audits"]) / 5, 1)) * 10
            + (1 - float(values["uses_zk_proof"])) * 8
        ) * 1.2

    if isinstance(raw_score, list):
        raw_score = raw_score[0]

    score = min(100.0, round(float(raw_score), 1))
    risk_label, risk_category = _bridge_category(score)
    return {
        "risk_score": score,
        "risk_label": risk_label,
        "risk_category": risk_category,
        "breakdown": {
            "custody_risk": round((1 - float(values["multisig_threshold"])) * 0.9, 2),
            "technical_risk": round((1 - float(values["uses_zk_proof"])) * 0.7, 2),
            "operational_risk": round(max(0, 1 - min(float(values["time_lock_hours"]) / 72, 1)) * 0.8, 2),
            "liquidity_risk": round(min(float(values["tvl_usd"]) / 1_000_000_000, 1.0) * 0.65, 2),
            "track_record_risk": round(min(float(values["prior_incidents"]) / 3, 1) * 0.95, 2),
        },
    }


def _shape_protocol_health_result(model_output: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    tvl = 100 - max(0, abs(float(values["tvl_7d_change"])) * 120) - float(values["tvl_top3_pool_concentration"]) * 20
    security = 45 + min(float(values["audit_count"]) * 10, 25) + min(float(values["timelock_hours"]) / 4, 20)
    decentralization = 100 - float(values["governance_token_gini"]) * 45 - float(values["top10_holder_share"]) * 35
    market = 45 + min(float(values["volume_to_tvl_ratio_7d"]) * 60, 25) + min(float(values["user_growth_rate_30d"]) * 120, 20)
    treasury = min(float(values["treasury_runway_months"]) * 2.2, 75) + float(values["stablecoin_share_of_treasury"]) * 25
    pillar_scores = {
        "tvl_health": round(max(0, min(100, tvl)), 1),
        "smart_contract_security": round(max(0, min(100, security)), 1),
        "decentralization": round(max(0, min(100, decentralization)), 1),
        "market_activity": round(max(0, min(100, market)), 1),
        "treasury_health": round(max(0, min(100, treasury)), 1),
    }
    score = round(
        pillar_scores["tvl_health"] * 0.30
        + pillar_scores["smart_contract_security"] * 0.25
        + pillar_scores["decentralization"] * 0.20
        + pillar_scores["market_activity"] * 0.15
        + pillar_scores["treasury_health"] * 0.10,
        1,
    )
    flags = []
    if float(values["timelock_hours"]) < 24 and float(values["is_upgradeable"]) >= 1:
        flags.append("NO_TIMELOCK")
    if float(values["exploit_history_count"]) > 0:
        flags.append("EXPLOIT_HISTORY")
    if float(values["treasury_runway_months"]) < 6:
        flags.append("LOW_TREASURY_RUNWAY")
    if float(values["native_token_share_of_treasury"]) > 0.70:
        flags.append("NATIVE_TOKEN_TREASURY_RISK")
    grade = "A+" if score >= 90 else "A" if score >= 80 else "B" if score >= 70 else "C" if score >= 60 else "D" if score >= 40 else "F"
    return {
        "health_score": score,
        "grade": grade,
        "pillar_scores": pillar_scores,
        "flags": flags,
        "summary": "Protocol health is driven by security, decentralization, activity, and treasury resilience.",
    }


def _shape_stablecoin_result(model_output: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    reserve = (max(0, 2 - float(values["collateral_ratio"])) * 30) + max(0, -float(values["reserve_change_7d"])) * 100
    market = float(values["peg_deviation_pct"]) * 1400 + max(0, float(values["dex_volume_7d_change"])) * 25
    liquidity = max(0, 20 - min(float(values["dex_liquidity_usd"]) / 5_000_000, 20)) + float(values["pool_concentration"]) * 40
    velocity = max(0, float(values["transfer_volume_7d_change"])) * 25 + float(values["whale_outflow_7d"]) * 120
    pillar_scores = {
        "reserve_adequacy": round(max(0, min(100, reserve)), 1),
        "market_stress": round(max(0, min(100, market)), 1),
        "liquidity_depth": round(max(0, min(100, liquidity)), 1),
        "on_chain_velocity": round(max(0, min(100, velocity)), 1),
    }
    score = round(
        pillar_scores["reserve_adequacy"] * 0.35
        + pillar_scores["market_stress"] * 0.30
        + pillar_scores["liquidity_depth"] * 0.20
        + pillar_scores["on_chain_velocity"] * 0.15,
        1,
    )
    alert = "STABLE" if score <= 25 else "WATCH" if score <= 50 else "WARNING" if score <= 75 else "CRITICAL"
    return {
        "depeg_risk_score": score,
        "alert": alert,
        "pillar_scores": pillar_scores,
    }


def _shape_dex_liquidity_exit_result(model_output: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    depth = (
        max(0, 35 - min(float(values["pool_tvl_usd"]) / 20_000_000, 35))
        + min(float(values["slippage_100k_buy_pct"]) * 1200, 40)
        + min(float(values["slippage_100k_sell_pct"]) * 1200, 25)
    )
    concentration = (
        float(values["lp_top10_share"]) * 60
        + float(values["top_pool_share_of_protocol"]) * 20
        + float(values["bridge_dependent_liquidity_share"]) * 20
    )
    flow = (
        max(0, -float(values["liquidity_7d_change"])) * 180
        + max(0, -float(values["net_swap_flow_7d"])) * 120
        + float(values["whale_lp_exit_7d"]) * 180
    )
    incentives = (
        min(float(values["emissions_to_fees_ratio"]) * 24, 55)
        + max(0, float(values["incentive_apr"]) - float(values["fee_apr"])) * 90
        + min(float(values["token_unlock_30d_usd"]) / 2_500_000, 20)
    )
    governance = (
        max(0, 24 - min(float(values["governance_timelock_hours"]) / 3, 24))
        + max(0, 12 - min(float(values["audit_count"]) * 4, 12))
        + min(float(values["exploit_history_count"]) * 16, 24)
        + float(values["oracle_dependency_score"]) * 18
        + float(values["correlated_asset_risk"]) * 12
    )
    pillar_scores = {
        "liquidity_depth": round(max(0, min(100, depth)), 1),
        "concentration_risk": round(max(0, min(100, concentration)), 1),
        "flow_instability": round(max(0, min(100, flow)), 1),
        "incentive_dependence": round(max(0, min(100, incentives)), 1),
        "governance_safety": round(max(0, min(100, governance)), 1),
    }
    score = round(
        pillar_scores["liquidity_depth"] * 0.28
        + pillar_scores["concentration_risk"] * 0.22
        + pillar_scores["flow_instability"] * 0.22
        + pillar_scores["incentive_dependence"] * 0.18
        + pillar_scores["governance_safety"] * 0.10,
        1,
    )
    risk_level = "LOW" if score <= 25 else "MEDIUM" if score <= 50 else "HIGH" if score <= 75 else "CRITICAL"
    flags: list[str] = []
    if float(values["lp_top10_share"]) > 0.60:
        flags.append("LP_CONCENTRATION")
    if float(values["whale_lp_exit_7d"]) > 0.10:
        flags.append("WHALE_EXIT_PRESSURE")
    if float(values["emissions_to_fees_ratio"]) > 1.25:
        flags.append("INCENTIVE_DEPENDENCE")
    if float(values["governance_timelock_hours"]) < 24:
        flags.append("SHORT_TIMELOCK")
    if float(values["slippage_100k_buy_pct"]) > 0.02:
        flags.append("SHALLOW_DEPTH")
    return {
        "liquidity_exit_risk_score": score,
        "grade": _grade_from_score(score),
        "risk_level": risk_level,
        "pillar_scores": pillar_scores,
        "flags": flags or ["NO_MAJOR_TRIGGER"],
    }


def _shape_nft_result(model_output: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    overlap = float(values["wallet_overlap_score"]) * 0.7
    cadence = max(0, 1 - min(float(values["time_delta_sec"]) / 120, 1)) * 0.15
    freshness = max(0, 1 - min((float(values["buyer_tx_count"]) + float(values["seller_tx_count"])) / 20, 1)) * 0.1
    gas = min(float(values["gas_paid_gwei"]) / 100, 1) * 0.05
    prob = round(min(0.99, overlap + cadence + freshness + gas), 2)
    return {
        "wash_probability": prob,
        "verdict": "wash_trading" if prob >= 0.5 else "legitimate",
    }


def _shape_generic_result(model: ModelDefinition, model_output: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    if model_output:
        generic = {key: _scalarize(value) for key, value in model_output.items()}
    else:
        generic = {}

    numeric_values = [
        float(value)
        for value in values.values()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    if numeric_values:
        normalized = []
        for value in numeric_values[:12]:
            if 0 <= value <= 1:
                normalized.append(value * 100)
            elif value <= 100:
                normalized.append(value)
            else:
                normalized.append(min(100.0, np.log10(value + 1) * 18))
        generic_score = round(float(sum(normalized) / max(len(normalized), 1)), 1)
    else:
        generic_score = 50.0

    score_key = next((key for key in model.result_keys if "score" in key.lower()), None)
    if score_key and score_key not in generic:
        generic[score_key] = generic_score
    if "generic_score" not in generic and not any("score" in key.lower() for key in generic):
        generic["generic_score"] = generic_score
    if not any(key.lower() in {"verdict", "grade", "label", "risk_category"} for key in generic):
        generic["verdict"] = "high signal" if generic_score >= 67 else "mixed signal" if generic_score >= 34 else "low signal"
    if "summary" not in generic:
        generic["summary"] = (
            f"Generic fallback result for {model.title}. Review the model-specific output keys and inputs because this Hub model is not part of the curated OG Runner shape set."
        )

    return generic


def _build_explanation(model: ModelDefinition, result: dict[str, Any]) -> str:
    if model.slug == "governance-capture-risk-scorer":
        score = result["governance_capture_risk_score"]
        grade = result["grade"]
        return (
            f"This model reads the protocol as {grade} grade governance risk with a score of {score}. "
            f"The main drivers are holder concentration, insider control, and proposal attack surface. "
            f"Use the flags to explain exactly why the governance setup is resilient or fragile."
        )

    if model.slug == "cross-chain-bridge-risk-classifier":
        score = result["risk_score"]
        category = result["risk_category"]
        return (
            f"This bridge profile comes back as {category} risk with a score of {score}. "
            f"The biggest contributors are custody design, verification stack, timelock strength, and incident history. "
            f"Use the breakdown as the operator checklist for what must improve before the bridge is safer."
        )
    if model.slug == "defi-protocol-health-score":
        return (
            f"This protocol health model gives a score of {result['health_score']} with grade {result['grade']}. "
            f"Read the pillar scores as an institutional diligence grid: capital stability, security, decentralization, market traction, and treasury endurance."
        )
    if model.slug == "dex-liquidity-exit-risk-scorer":
        return (
            f"This DEX liquidity model gives a score of {result['liquidity_exit_risk_score']} with {result['risk_level']} risk. "
            f"Use the pillar scores to see whether the fragility comes from shallow depth, LP concentration, unstable flows, or incentive-heavy liquidity."
        )
    if model.slug == "stablecoin-depeg-risk-monitor":
        return (
            f"This stablecoin currently sits at {result['alert']} with a depeg risk score of {result['depeg_risk_score']}. "
            f"The four pillar scores tell you whether the problem is reserves, market behavior, liquidity, or wallet-flight velocity."
        )
    if model.slug == "nft-wash-trading-detector":
        return (
            f"This NFT transaction scores {result['wash_probability']} wash probability and is currently classified as {result['verdict']}. "
            f"Wallet overlap and abnormal trading cadence are the main signals to inspect first."
        )
    return (
        f"{model.title} is running as a custom Hub model. "
        f"The runner inferred its inputs and outputs from the Hub description, so use the model-specific fields and review the returned keys directly. "
        f"Current output keys: {', '.join(list(result.keys())[:6]) or 'generic_score, verdict, summary'}."
    )


def _build_llm_prompt(
    *,
    message: str,
    model: ModelDefinition | None = None,
    result: dict[str, Any] | None = None,
    normalized_input: dict[str, Any] | None = None,
    target_url: str | None = None,
) -> str:
    context = {
        "message": message,
        "target_url": target_url,
        "model": model.model_dump() if model else None,
        "result": result or {},
        "normalized_input": normalized_input or {},
    }
    return (
        "You are the OG Runner assistant for OpenGradient models. "
        "Explain clearly what a model does, how it evaluates risk or health, what the current score means, "
        "and what the most important drivers are. If asked to search models, recommend the most relevant models "
        "from the provided registry context only. Be concise, concrete, and product-facing.\n\n"
        f"Context JSON:\n{json.dumps(context, ensure_ascii=False, default=str)}"
    )


def generate_assistant_answer(
    *,
    message: str,
    model: ModelDefinition | None = None,
    result: dict[str, Any] | None = None,
    normalized_input: dict[str, Any] | None = None,
    target_url: str | None = None,
    llm_model: str | None = None,
) -> tuple[str, Literal["opengradient_llm", "local_fallback"], str]:
    global _llm_cooldown_until
    resolved_llm_model = resolve_tee_llm_model_name(llm_model)

    fallback = (
        _build_explanation(model, result or {})
        if model and result
        else (
            f"{model.title}: {model.summary} {model.guide.what_it_does}"
            if model
            else "OG Runner can explain the selected model, summarize its scoring logic, and suggest the most relevant model for a protocol, bridge, DEX, stablecoin, or NFT use case."
        )
    )

    if not supports_live_llm():
        return fallback, "local_fallback", resolved_llm_model

    try:
        llm = _get_llm_client()
        response = llm.completion(
            model=_get_tee_llm_model_by_name(resolved_llm_model),
            prompt=_build_llm_prompt(
                message=message,
                model=model,
                result=result,
                normalized_input=normalized_input,
                target_url=target_url,
            ),
            max_tokens=260,
            temperature=0.2,
            x402_settlement_mode=og.x402SettlementMode.PRIVATE,
        )
        answer = _extract_llm_text(_await_llm_response(response))
        return (answer or fallback), "opengradient_llm", resolved_llm_model
    except Exception:
        _llm_cooldown_until = monotonic() + _LLM_COOLDOWN_SECONDS
        return fallback, "local_fallback", resolved_llm_model


def get_wallet_preflight() -> dict[str, Any]:
    issues: list[str] = []
    if not settings.og_private_key or og is None:
        return {
            "wallet_address": None,
            "base_sepolia_eth": None,
            "opg_balance": None,
            "permit2_allowance": None,
            "llm_ready": False,
            "live_inference_ready": False,
            "issues": ["OG_PRIVATE_KEY is not configured."],
        }

    try:
        import opengradient.client.opg_token as opg_token

        llm = _get_llm_client()
        owner = Web3.to_checksum_address(llm._wallet_account.address)
        w3, token, spender = opg_token._get_web3_and_contract()
        eth_balance = float(w3.eth.get_balance(owner)) / 10**18
        opg_balance = float(token.functions.balanceOf(owner).call()) / 10**18
        allowance = float(token.functions.allowance(owner, spender).call()) / 10**18

        if eth_balance <= 0:
            issues.append("Wallet has no Base Sepolia ETH for gas.")
        if opg_balance <= 0:
            issues.append("Wallet has no OPG balance.")
        if allowance < 0.1:
            issues.append("Permit2 OPG allowance is below 0.1 OPG for TEE LLM payments.")

        return {
            "wallet_address": owner,
            "base_sepolia_eth": eth_balance,
            "opg_balance": opg_balance,
            "permit2_allowance": allowance,
            "llm_ready": eth_balance > 0 and opg_balance > 0 and allowance >= 0.1,
            "live_inference_ready": eth_balance > 0,
            "issues": issues,
        }
    except Exception as exc:
        return {
            "wallet_address": None,
            "base_sepolia_eth": None,
            "opg_balance": None,
            "permit2_allowance": None,
            "llm_ready": False,
            "live_inference_ready": False,
            "issues": [f"Wallet preflight failed: {exc}"],
        }


def _shape_result(model: ModelDefinition, model_output: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    if model.slug == "governance-capture-risk-scorer":
        return _shape_governance_result(model_output, values)
    if model.slug == "cross-chain-bridge-risk-classifier":
        return _shape_bridge_result(model_output, values)
    if model.slug == "defi-protocol-health-score":
        return _shape_protocol_health_result(model_output, values)
    if model.slug == "dex-liquidity-exit-risk-scorer":
        return _shape_dex_liquidity_exit_result(model_output, values)
    if model.slug == "stablecoin-depeg-risk-monitor":
        return _shape_stablecoin_result(model_output, values)
    if model.slug == "nft-wash-trading-detector":
        return _shape_nft_result(model_output, values)
    return _shape_generic_result(model, model_output, values)


def run_demo(model: ModelDefinition, inputs: dict[str, Any]) -> ExecutionResult:
    """Return a deterministic demo result shaped like the real model output."""
    warnings: list[str] = []
    extracted_inputs, extraction_warnings = infer_inputs_from_url(model, inputs.get("target_url"))
    values = {**model.sample_input, **extracted_inputs, **inputs}
    result = _shape_result(model, {}, values)
    explanation, explanation_source, _ = generate_assistant_answer(
        message="Explain what this model does, how it scored the target, and what the main drivers are.",
        model=model,
        result=result,
        normalized_input=values,
        target_url=inputs.get("target_url"),
    )
    warnings.extend(extraction_warnings)
    if explanation_source == "local_fallback":
        if settings.og_private_key and not settings.og_enable_live_llm:
            warnings.append("OpenGradient LLM explanations are currently disabled in backend settings. Using local fallback.")
        else:
            warnings.append("OpenGradient LLM assistant is not configured; local explanation fallback used.")

    return ExecutionResult(
        normalized_input=values,
        result=result,
        ai_explanation=explanation,
        warnings=warnings,
        execution_mode="demo",
        transaction_hash=None,
    )


def run_live(model: ModelDefinition, inputs: dict[str, Any]) -> ExecutionResult:
    """Run real OpenGradient Alpha inference and map the output into OG Runner shape."""
    if not supports_live_inference():
        raise RuntimeError("OpenGradient live inference is not configured.")

    extracted_inputs, extraction_warnings = infer_inputs_from_url(model, inputs.get("target_url"))
    values = {**model.sample_input, **extracted_inputs, **inputs}
    alpha = _get_alpha_client()
    inference_result = alpha.infer(
        model_cid=model.model_cid,
        inference_mode=og.InferenceMode.VANILLA,
        model_input=_build_live_model_input(model, values),
    )
    raw_output = _scalarize(inference_result.model_output)
    result = _shape_result(model, raw_output, values)
    explanation, explanation_source, _ = generate_assistant_answer(
        message="Explain what this model does, how it scored the target, and what the main drivers are.",
        model=model,
        result=result,
        normalized_input=values,
        target_url=inputs.get("target_url"),
    )

    warnings: list[str] = extraction_warnings
    if explanation_source == "local_fallback":
        if settings.og_private_key and not settings.og_enable_live_llm:
            warnings.append("OpenGradient LLM explanations are currently disabled in backend settings. Using local fallback.")
        else:
            warnings.append("OpenGradient LLM assistant is not configured; local explanation fallback used.")

    return ExecutionResult(
        normalized_input=values,
        result=result,
        ai_explanation=explanation,
        warnings=warnings,
        execution_mode="live",
        transaction_hash=inference_result.transaction_hash,
    )
