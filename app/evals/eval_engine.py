class EvalEngine:

    def log_run(self, agent, success, latency, metadata):
        return {
            "agent": agent,
            "success": success,
            "latency": latency,
            "meta": metadata
        }

    def score_system(self, runs):
        success_rate = sum(r["success"] for r in runs) / len(runs)

        avg_latency = sum(r["latency"] for r in runs) / len(runs)

        return {
            "success_rate": success_rate,
            "avg_latency": avg_latency
        }
