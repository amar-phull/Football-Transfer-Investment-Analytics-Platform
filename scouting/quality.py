"""Reconcile Pandas subject coverage against the staged PostgreSQL transaction."""
import pandas as pd


def reconcile(db, snapshot, observations, metrics):
    staged = pd.DataFrame.from_records(
        ((stint, subject) for stint,subject,_,_ in metrics), columns=["stint","subject"])
    if staged.duplicated().any() or staged["stint"].nunique() != len(observations):
        raise ValueError("Staged performance does not reconcile to the stint union")
    expected = staged.groupby("subject").size().to_dict()
    actual = dict(db.run("""SELECT f.subject,count(*) FROM performance f
        JOIN stint s ON s.id=f.stint WHERE s.snapshot=? GROUP BY f.subject""",(snapshot,)))
    if actual != expected:
        raise ValueError(f"Persisted subject counts differ: {actual}")
