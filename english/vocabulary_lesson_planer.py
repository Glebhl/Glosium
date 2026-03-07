from typing import List
from agent import Agent


class VocabluaryLessonPlanner:
    def __init__(self, agent, native_language) -> None:
        # Save passed variables
        self.agent: Agent = agent
        self.native_language = native_language

        # Lesson vaiables
        self.query: List[str] = []
        self.lesson_plan_raw: str = "EMPTY"
        self.lesson_plan_parsed: List[dict] = []
    
    def plan(self, query: str) -> List[dict]:
        try:
            # Load prompt
            with open("prompts/planner.txt", "r") as f:
                prompt = f.read()
            
            # Fromat prompt
            prompt = prompt.format(
                query=query,
                lesson_plan=self.lesson_plan_raw,
                native_language=self.native_language,
            )

            # Procces prompt
            self.lesson_plan_raw = self.agent.process(prompt, max_new_tokens=1024)
            print(self.lesson_plan_raw)

            # Parse prompt
            self.lesson_plan_parsed = [
                dict(line.split(": ", 1) for line in block.splitlines())
                for block in self.lesson_plan_raw.strip().split("\n\n")
            ]
        except Exception as e:
            print(e)
        
        return self.lesson_plan_parsed
    
    def _process_query(self) -> None:
        pass

    def _generate_translation_task(self, words, audio: bool) -> None:
        pass
    
    def _generate_matching_task(self, audio: bool):
        pass

    def _generate_gap_task(self, words: List[str]):
        pass
    
    def _generate_question_task(self, words: List[str]):
        pass

    def _generate_info() -> List[str]:
        pass