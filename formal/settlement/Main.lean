/-
  `lake exe settlement-table` prints the model's outputs as JSON, so the
  cross-check tests can compare them with the real implementations.
  The committed copy is model_table.json; CI regenerates and diffs it.
-/
import Settlement

open Settlement

def q (s : String) : String := "\"" ++ s ++ "\""
def jbool (b : Bool) : String := if b then "true" else "false"
def jarr (xs : List String) : String := "[" ++ ", ".intercalate xs ++ "]"
def jobj (kvs : List (String × String)) : String :=
  "{" ++ ", ".intercalate (kvs.map fun (k, v) => q k ++ ": " ++ v) ++ "}"

def splitInputs : List Nat :=
  (List.range 241) ++
  [999, 1000, 1010, 1020, 4000, 19999, 20000, 20001, 20020, 123456780, 123456789,
   1000000000000, 1000000000020, 1000000000010,
   -- near the float64 exact-integer limit (2^53 = 9007199254740992) for t * 9000
   1000799917193440, 1000799917193460, 1000799917193450,
   9007199254740980, 9007199254740992]

def splitRow (t : Nat) : String :=
  let sc := match splitContribution t with
    | some (w, a, b) => jarr [toString w, toString a, toString b]
    | none => "null"
  jobj [("t", toString t), ("worker", toString (workerShare t)),
        ("verifier", toString (verifierShare t)), ("clean", jbool (splitsClean t)),
        ("split", sc)]

def evidenceInputs : List (Nat × Nat × Nat × Nat) := Id.run do
  let mut out := []
  for c in [0, 20, 40, 1000, 1010, 4000, 20000] do
    for w in [workerShare c, workerShare c + 1, c] do
      for v1 in [verifierShare c, verifierShare c + 1, 0] do
        for v2 in [verifierShare c, 0] do
          out := out ++ [(w, v1, v2, c)]
  return out

def verdicts : List Verdict := [.parentEmpty, .childEmpty, .agree, .disagreeDeterministic]
def ids : List String := ["", "a", "b", "c"]

def flowScenarios : List (String × List Ev) :=
  [("agree_agree", [.first "b" .agree, .second "c" .agree]),
   ("disagree_tiebreak_disagree", [.first "b" .disagreeDeterministic, .tiebreak "c" .disagreeDeterministic]),
   ("disagree_tiebreak_agree_second_agree",
     [.first "b" .disagreeDeterministic, .tiebreak "c" .agree, .second "d" .agree]),
   ("agree_second_disagree", [.first "b" .agree, .second "c" .disagreeDeterministic]),
   ("agree_second_disagree_tiebreak_agree",
     [.first "b" .agree, .second "c" .disagreeDeterministic, .tiebreak "d" .agree]),
   ("agree_second_disagree_tiebreak_disagree",
     [.first "b" .agree, .second "c" .disagreeDeterministic, .tiebreak "d" .disagreeDeterministic]),
   ("disagree_tiebreak_agree_second_disagree",
     [.first "b" .disagreeDeterministic, .tiebreak "c" .agree, .second "d" .disagreeDeterministic])]

def evJson : Ev → String
  | .first c v => jobj [("check", q "first"), ("node", q c), ("verdict", q v.tag)]
  | .second c v => jobj [("check", q "second"), ("node", q c), ("verdict", q v.tag)]
  | .tiebreak c v => jobj [("check", q "tiebreak"), ("node", q c), ("verdict", q v.tag)]

def paidTo (s : St) (n : String) : Nat :=
  (s.checkerPays.filter (·.1 == n)).foldl (fun acc p => acc + p.2) 0

def flowRow (name : String) (evs : List Ev) : String :=
  let j : Job := { worker := "a", award := 4, digestsOk := true }
  let s := run j evs
  jobj [("name", q name), ("events", jarr (evs.map evJson)),
        ("status", q s.status.tag), ("amount", toString s.amount),
        ("mesh_credits", toString s.meshCredits),
        ("worker_balance", toString s.workerBal), ("credits_awarded", toString s.credited),
        ("verifier1", q s.v1), ("verifier2", q s.v2),
        ("tiebreak_queued", jbool s.tiebreakOpen),
        ("checker_balance", jobj (["b", "c", "d"].map fun n => (n, toString (paidTo s n))))]

def main : IO Unit := do
  let split := splitInputs.map splitRow
  let ev := evidenceInputs.map fun (w, v1, v2, c) =>
    jobj [("w", toString w), ("v1", toString v1), ("v2", toString v2), ("c", toString c),
          ("ok", jbool (evidenceSplitOk w v1 v2 c))]
  let pay := verdicts.map fun v => jobj [("verdict", q v.tag), ("pay", toString (checkerPay v))]
  let ind := Id.run do
    let mut out := []
    for w in ids do
      for a in ids do
        for b in ids do
          out := out ++ [jobj [("worker", q w), ("a", q a), ("b", q b),
                               ("independent", jbool (independent w a b))]]
    return out
  let flow := flowScenarios.map fun (n, e) => flowRow n e
  IO.println (jobj [("units_per_credit", toString UNITS_PER_CREDIT),
                    ("verifier_pay", toString VERIFIER_PAY),
                    ("split", jarr split), ("evidence_split_ok", jarr ev),
                    ("checker_pay", jarr pay), ("independent", jarr ind), ("flow", jarr flow)])
