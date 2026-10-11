"""Operational tables for the action layer (PostgreSQL). These are written by the API and the simulated
clock; they never touch the monthly marts. `reset()` recreates them from a clean, seeded start."""
from __future__ import annotations

from sqlalchemy import text

from ..db import copy_df, engine

DDL = """
DROP TABLE IF EXISTS resupply_request, field_verification, inbound_response, message, case_event, case_file,
                     sim_clock, mart_facility_live, action_suggestion CASCADE;
DROP SEQUENCE IF EXISTS case_seq, message_seq, response_seq, verification_seq, resupply_seq, digest_seq;
CREATE SEQUENCE case_seq START 1001; CREATE SEQUENCE message_seq START 1; CREATE SEQUENCE response_seq START 1;
CREATE SEQUENCE verification_seq START 1; CREATE SEQUENCE resupply_seq START 1; CREATE SEQUENCE digest_seq START 1;

CREATE TABLE sim_clock (id int PRIMARY KEY DEFAULT 1, sim_date date NOT NULL, started date NOT NULL,
                        baseline_month text NOT NULL, CHECK (id = 1));

CREATE TABLE case_file (
  case_id text PRIMARY KEY, case_ref text UNIQUE NOT NULL, level text NOT NULL,
  state_code text NOT NULL, lga_id text, facility_id text, unit_id text NOT NULL,
  rule_id text NOT NULL, playbook_id text NOT NULL, priority text NOT NULL, base_priority text NOT NULL,
  priority_notes jsonb NOT NULL DEFAULT '[]', status text NOT NULL,
  owner_person_id text, owner_role text NOT NULL, raised_by_person_id text,
  opened_at date NOT NULL, due_at date NOT NULL, acknowledged_at date, resolved_at date,
  last_activity_at date NOT NULL, current_step int NOT NULL DEFAULT 0,
  escalation_level int NOT NULL DEFAULT 0, escalation_ladder text, escalated_to_person_id text,
  escalated_to_role text, evidence_snapshot jsonb, baseline_month text NOT NULL,
  outcome_code text, outcome_note text, response_lead text, response_plan text,
  synthetic_actor boolean NOT NULL DEFAULT false, demo boolean NOT NULL DEFAULT false,
  demo_script jsonb, report_ingest_due date, review_task boolean NOT NULL DEFAULT false);
CREATE INDEX ON case_file (state_code, status, priority);
CREATE INDEX ON case_file (state_code, lga_id, status);
CREATE INDEX ON case_file (facility_id);
CREATE INDEX ON case_file (owner_person_id);
CREATE INDEX ON case_file (escalated_to_person_id);
CREATE INDEX ON case_file (unit_id, playbook_id);

CREATE TABLE case_event (
  event_id bigserial PRIMARY KEY, case_id text NOT NULL REFERENCES case_file(case_id), at date NOT NULL,
  seq bigint NOT NULL DEFAULT 0, actor_person_id text, actor text NOT NULL, event_type text NOT NULL,
  from_status text, to_status text, payload jsonb, synthetic_actor boolean NOT NULL DEFAULT false);
CREATE INDEX ON case_event (case_id, event_id);

CREATE TABLE message (
  message_id text PRIMARY KEY, case_id text REFERENCES case_file(case_id), to_person_id text NOT NULL,
  state_code text NOT NULL, lga_id text, channel text NOT NULL, template_id text NOT NULL, kind text NOT NULL,
  priority text NOT NULL, body text NOT NULL, chars int NOT NULL, status text NOT NULL,
  created_at date NOT NULL, approved_by text, approved_at date, scheduled_for date, sent_at date,
  delivered_at date, digest_id text, step_id text, expects text, synthetic boolean NOT NULL DEFAULT true,
  -- simulation internals (never shown as data): the planned simulated reply
  planned_reply_at date, planned_reply_text text);
CREATE INDEX ON message (state_code, status);
CREATE INDEX ON message (case_id);
CREATE INDEX ON message (to_person_id, status);

CREATE TABLE inbound_response (
  response_id text PRIMARY KEY, message_id text REFERENCES message(message_id), case_id text,
  from_person_id text NOT NULL, state_code text NOT NULL, received_at date NOT NULL, raw_text text NOT NULL,
  parsed jsonb, parse_status text NOT NULL, review_status text NOT NULL DEFAULT 'none',
  reviewed_by text, synthetic boolean NOT NULL DEFAULT true);
CREATE INDEX ON inbound_response (state_code, parse_status, review_status);

CREATE TABLE field_verification (
  verification_id text PRIMARY KEY, facility_id text NOT NULL, state_code text NOT NULL, verified_at date NOT NULL,
  source text NOT NULL, commodity_code text, quantity double precision, fridge_functional boolean,
  reports_submitted boolean, by_person_id text, case_id text, response_id text,
  synthetic boolean NOT NULL DEFAULT true);
CREATE INDEX ON field_verification (facility_id, verified_at);

CREATE TABLE resupply_request (
  request_id text PRIMARY KEY, case_id text REFERENCES case_file(case_id), facility_id text NOT NULL,
  state_code text NOT NULL, lga_id text, commodity_code text NOT NULL, qty_requested double precision NOT NULL,
  basis text NOT NULL, status text NOT NULL, requested_by text, requested_at date NOT NULL,
  approved_by text, approved_at date, expected_delivery date, delivered_at date,
  synthetic boolean NOT NULL DEFAULT true);
CREATE INDEX ON resupply_request (state_code, status);

CREATE TABLE action_suggestion (
  state_code text PRIMARY KEY, rule_id text NOT NULL, reason text NOT NULL, baseline_month text NOT NULL);
"""


def recreate(conn) -> None:
    conn.execute(text(DDL))


def load_directory(conn, roles, people) -> None:
    copy_df(conn, roles, "dim_role")
    copy_df(conn, people, "dim_person")
    conn.execute(text("""
        ALTER TABLE dim_person ADD PRIMARY KEY (person_id);
        CREATE INDEX ON dim_person (state_code, role_code, lga_id);
        CREATE INDEX ON dim_person (facility_id);
        ALTER TABLE dim_role ADD PRIMARY KEY (role_code);
    """))


def tables_exist() -> bool:
    with engine().connect() as c:
        return bool(c.execute(text("SELECT to_regclass('case_file')")).scalar())
