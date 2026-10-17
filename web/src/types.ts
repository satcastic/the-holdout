// Mirrors the whitelisted response models in src/api.py. No hidden fields exist here.

export interface SuspectCard {
  id: string;
  name: string;
  role: string;
  bio: string;
}

export interface SessionCreated {
  session_id: string;
  title: string;
  premise: string;
  setting: string;
  intro: string;
  victim_name: string;
  victim_role: string;
  suspects: SuspectCard[];
  turns_left: number;
  start_turns: number;
}

export interface ClueEntry {
  id: string;
  notebook: string;
  source_title: string;
  source_type: string;
}

export interface Breakdown {
  suspect: number;
  alibi: number;
  eliminations: number;
  motive: number;
  turns: number;
}

export interface Verdict {
  accused: string;
  accused_name: string;
  correct: boolean;
  grade: "full_credit" | "partial_credit" | "wrong" | "case_lost";
  score: number;
  breakdown: Breakdown;
  cleared_suspects: string[];
  counted_clues: string[];
  feedback: string;
  accusations_left: number;
}

export interface GameStatus {
  session_id: string;
  turns_left: number;
  start_turns: number;
  discovered: ClueEntry[];
  suspects_questioned: string[];
  current_focus: string | null;
  accusations_left: number;
  game_over: boolean;
  verdict: Verdict | null;
}

export interface TurnState extends GameStatus {
  new_clues: ClueEntry[];
}

export type ActionKind =
  | "question_suspect"
  | "present_evidence"
  | "examine_scene"
  | "request_records"
  | "ask_forensics"
  | "accuse";

export interface Action {
  kind: ActionKind;
  suspect_id?: string | null;
  clue_ids?: string[];
  reasoning?: string | null;
}

export interface AccuseResult {
  reply: string;
  verdict: Verdict;
  state: GameStatus;
}

export interface TimelineEvent {
  day: string;
  start: string;
  end: string;
  who: string[];
  location: string;
  event: string;
}

export interface Reveal {
  killer: string;
  killer_name: string;
  weapon: string;
  method: string;
  staging: string;
  time_of_death: string;
  location: string;
  alibi_flaw: string;
  clue_chain: string[];
  timeline: TimelineEvent[];
}

export interface TranscriptEntry {
  id: number;
  speaker: string; // "player" | "narrator" | "records" | "scene" | "forensics" | suspect id
  text: string;
  newClues?: ClueEntry[];
}
