"""Логика одной тренировки.

В этом файле нет ни одного упоминания Telegram. Это сделано специально:
логику можно проверить обычным Python-скриптом (см. test_quiz.py), не запуская
бота и не имея токена.

Одна тренировка = один объект Session. У каждого пользователя свой объект,
поэтому два человека не мешают друг другу.
"""

from questions import ADVICE, ADVICE_NO_MISTAKES, DONT_KNOW, QUESTIONS

TOTAL = len(QUESTIONS)


class Answer:
    """Что вернуть пользователю после одного ответа."""

    def __init__(self, is_correct, is_dont_know, answer_text, explanation):
        self.is_correct = is_correct
        self.is_dont_know = is_dont_know
        self.answer_text = answer_text
        self.explanation = explanation


class Session:
    """Состояние одной тренировки одного пользователя.

    index  — номер задания, которое сейчас на экране (нумерация с 0)
    score  — сколько верных ответов
    log    — что ответили на каждое задание, по порядку
    """

    def __init__(self):
        self.index = 0
        self.score = 0
        self.log = []

    # --- где мы сейчас ---------------------------------------------------

    def is_finished(self):
        """Все пять заданий отвечены."""
        return self.index >= TOTAL

    def current(self):
        """Задание, которое сейчас нужно показать. None, если тренировка кончилась."""
        if self.is_finished():
            return None
        return QUESTIONS[self.index]

    def number(self):
        """Номер текущего задания для подписи «N из 5»."""
        return self.index + 1

    # --- ответ -----------------------------------------------------------

    def submit(self, question_index, option_index):
        """Принять ответ на задание номер question_index.

        Возвращает Answer, если ответ принят, и None, если ответ не приняли.

        None возвращается, когда пользователь нажал старую кнопку: например,
        прокрутил чат вверх и нажал кнопку уже отвеченного задания, или нажал
        одну и ту же кнопку два раза подряд. Балл в этих случаях не начисляется,
        поэтому счёт не может стать больше пяти.
        """
        if question_index != self.index:
            return None  # кнопка не от текущего задания — молча игнорируем

        question = QUESTIONS[question_index]
        is_dont_know = option_index == DONT_KNOW
        is_correct = (not is_dont_know) and option_index == question["correct"]

        if is_correct:
            self.score += 1
            explanation = question["if_correct"]
        else:
            explanation = question["if_wrong"]

        self.log.append(
            {
                "index": question_index,
                "rule": question["rule"],
                "is_correct": is_correct,
                "is_dont_know": is_dont_know,
            }
        )

        # Переходим к следующему заданию. Именно этот шаг защищает от двойного
        # нажатия: второе нажатие придёт с прежним question_index, а self.index
        # уже другой, и submit вернёт None.
        self.index += 1

        return Answer(
            is_correct=is_correct,
            is_dont_know=is_dont_know,
            answer_text=question["answer_text"],
            explanation=explanation,
        )

    # --- итог ------------------------------------------------------------

    def dont_know_count(self):
        return sum(1 for item in self.log if item["is_dont_know"])

    def advice(self):
        """Один короткий совет по признаку, в котором было больше всего ошибок."""
        mistakes = {}
        for item in self.log:
            if not item["is_correct"]:
                mistakes[item["rule"]] = mistakes.get(item["rule"], 0) + 1

        if not mistakes:
            return ADVICE_NO_MISTAKES

        # Самый частый признак ошибки. При равенстве берём тот, что встретился
        # раньше в списке заданий — так результат всегда одинаковый.
        worst_rule = max(mistakes, key=lambda rule: mistakes[rule])
        return ADVICE[worst_rule]

    def summary(self):
        """Текст итога: результат, нейтральная фраза и один совет."""
        lines = ["Готово: {} из {}.".format(self.score, TOTAL)]

        skipped = self.dont_know_count()
        if skipped == 1:
            lines.append("Одно задание ты отметил как «не знаю».")
        elif skipped > 1:
            lines.append("Заданий, отмеченных как «не знаю»: {}.".format(skipped))

        lines.append(self.advice())
        return "\n\n".join(lines)
