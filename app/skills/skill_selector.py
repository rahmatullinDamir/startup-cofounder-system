class SkillSelector:

    def select(self, agent, input_data, memory):

        if agent == "ideation":
            return "generate_idea.md" if len(memory) == 0 else "improve_idea.md"

        if agent == "critic":
            return "evaluate_deep.md" if len(memory) > 500 else "evaluate_basic.md"

        if agent == "planner":
            return "detailed_plan.md"