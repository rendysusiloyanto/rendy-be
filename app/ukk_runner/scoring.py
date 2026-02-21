class ScoreManager:
    def __init__(self):
        self.total_score = 0
        self.max_score = 0

    def add(self, result: dict):
        self.total_score += result["score"]
        self.max_score += result["max_score"]

    def summary(self):
        percentage = (self.total_score / self.max_score * 100) if self.max_score > 0 else 0
        grade = "A" if percentage >= 90 else "B" if percentage >= 80 else "C" if percentage >= 70 else "D"
        return {"total": self.total_score, "max": self.max_score, "percentage": round(percentage, 2), "grade": grade}
