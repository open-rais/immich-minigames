class MoreOrLessScoring:
    BASE = 100
    MULT = 25

    def calculate(self, is_correct: bool, streak: int) -> int:
        if not is_correct:
            return 0
        return self.BASE + streak * self.MULT
    
def calculate_score(streak: int) -> int:
    scoring = MoreOrLessScoring()
    return scoring.calculate(is_correct=True, streak=streak)
