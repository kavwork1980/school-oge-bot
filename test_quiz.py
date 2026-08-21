"""Простые проверки логики тренировки.

Запуск:
    python test_quiz.py

Никакого тестового фреймворка здесь нет специально: обычные assert работают
и понятны без дополнительных знаний. Telegram и токен для этих проверок
не нужны — проверяется только quiz.py и questions.py.
"""

from questions import ADVICE, DONT_KNOW, QUESTIONS
from quiz import TOTAL, Session


def test_five_questions():
    """Заданий ровно пять."""
    assert len(QUESTIONS) == 5, "заданий должно быть 5, а не {}".format(len(QUESTIONS))
    assert TOTAL == 5


def test_every_question_is_complete():
    """У каждого задания есть текст, кнопки, правильный ответ и объяснения."""
    for i, q in enumerate(QUESTIONS):
        assert q["text"].strip(), "задание {}: пустой текст".format(i)
        assert len(q["options"]) == 2, "задание {}: должно быть 2 кнопки".format(i)

        # Правильный ответ существует и указывает на реальную кнопку.
        assert q["correct"] in (0, 1), "задание {}: неверный номер ответа".format(i)
        assert q["options"][q["correct"]] == q["answer_text"], (
            "задание {}: answer_text не совпадает с правильной кнопкой".format(i)
        )

        # Объяснения есть и они разные для верного и неверного ответа.
        assert q["if_correct"].strip(), "задание {}: нет объяснения для верного".format(i)
        assert q["if_wrong"].strip(), "задание {}: нет объяснения для неверного".format(i)
        assert q["if_correct"] != q["if_wrong"], "задание {}: объяснения одинаковые".format(i)

        # Для признака задания есть совет в конце тренировки.
        assert q["rule"] in ADVICE, "задание {}: нет совета для признака {}".format(i, q["rule"])


def test_new_session_starts_from_zero():
    """Новая сессия начинается с нуля."""
    s = Session()
    assert s.index == 0
    assert s.score == 0
    assert s.log == []
    assert not s.is_finished()
    assert s.number() == 1


def test_all_correct_gives_five():
    """Пять верных ответов — результат 5 из 5."""
    s = Session()
    for i in range(TOTAL):
        result = s.submit(i, QUESTIONS[i]["correct"])
        assert result is not None
        assert result.is_correct

    assert s.score == 5
    assert s.is_finished()
    assert s.current() is None


def test_all_wrong_gives_zero():
    """Пять неверных ответов — результат 0 из 5."""
    s = Session()
    for i in range(TOTAL):
        wrong = 1 - QUESTIONS[i]["correct"]
        result = s.submit(i, wrong)
        assert result is not None
        assert not result.is_correct

    assert s.score == 0
    assert s.is_finished()


def test_score_can_not_exceed_five():
    """Счёт не может стать больше пяти, сколько ни нажимай."""
    s = Session()
    for i in range(TOTAL):
        s.submit(i, QUESTIONS[i]["correct"])

    # Пробуем нажать ещё раз на каждое задание — счёт не меняется.
    for i in range(TOTAL):
        assert s.submit(i, QUESTIONS[i]["correct"]) is None

    assert s.score == 5


def test_double_click_gives_one_point():
    """Двойное нажатие на один и тот же ответ даёт один балл, а не два."""
    s = Session()
    first = s.submit(0, QUESTIONS[0]["correct"])
    second = s.submit(0, QUESTIONS[0]["correct"])

    assert first is not None
    assert second is None, "второе нажатие должно игнорироваться"
    assert s.score == 1
    assert s.index == 1


def test_old_button_is_ignored():
    """Кнопка от старого задания не портит счёт текущего."""
    s = Session()
    s.submit(0, QUESTIONS[0]["correct"])  # ответили на задание 1
    s.submit(1, QUESTIONS[1]["correct"])  # ответили на задание 2

    assert s.score == 2
    assert s.submit(0, QUESTIONS[0]["correct"]) is None  # старая кнопка
    assert s.score == 2
    assert s.index == 2


def test_dont_know_is_not_correct():
    """«Не знаю» не засчитывается как верный ответ, но задание проходится."""
    s = Session()
    result = s.submit(0, DONT_KNOW)

    assert result is not None
    assert not result.is_correct
    assert result.is_dont_know
    assert s.score == 0
    assert s.index == 1
    assert s.dont_know_count() == 1


def test_two_users_do_not_mix():
    """У двух пользователей две независимые сессии."""
    a = Session()
    b = Session()

    a.submit(0, QUESTIONS[0]["correct"])
    a.submit(1, QUESTIONS[1]["correct"])

    assert a.score == 2
    assert b.score == 0
    assert b.index == 0


def test_restart_starts_from_zero():
    """Новая тренировка после законченной начинается с нуля."""
    s = Session()
    for i in range(TOTAL):
        s.submit(i, QUESTIONS[i]["correct"])
    assert s.score == 5

    s = Session()  # «Пройти ещё раз» создаёт новую сессию
    assert s.score == 0
    assert s.index == 0
    assert not s.is_finished()


def test_summary_mentions_result():
    """В итоге есть число и совет."""
    s = Session()
    for i in range(TOTAL):
        s.submit(i, QUESTIONS[i]["correct"])

    text = s.summary()
    assert "5 из 5" in text
    assert len(text.strip()) > 20


def test_advice_points_at_worst_rule():
    """Совет выбирается по признаку, в котором было больше всего ошибок."""
    s = Session()
    for i in range(TOTAL):
        # Задание 3 (индекс 2) — про зависимое слово, отвечаем на него неверно.
        if i == 2:
            s.submit(i, 1 - QUESTIONS[i]["correct"])
        else:
            s.submit(i, QUESTIONS[i]["correct"])

    assert s.score == 4
    assert s.advice() == ADVICE["dependent"]


def run_all():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]

    for test in tests:
        test()
        print("OK  {}".format(test.__name__))

    print("\nВсе проверки пройдены: {}".format(len(tests)))


if __name__ == "__main__":
    run_all()
