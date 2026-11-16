"""
CampusFlow - тесты на конфликты бронирований
"""
import pytest
from datetime import date, time
from app.services.conflicts import check_time_overlap, find_booking_conflicts, validate_booking_time


class TestTimeOverlap:
    """Тесты проверки пересечения временных интервалов"""
    
    def test_no_overlap_separate(self):
        """Интервалы не пересекаются (разделены)"""
        assert not check_time_overlap(
            time(10, 0), time(11, 0),
            time(12, 0), time(13, 0)
        )
    
    def test_no_overlap_touching_boundaries(self):
        """Касание границ НЕ считается конфликтом"""
        assert not check_time_overlap(
            time(10, 0), time(11, 0),
            time(11, 0), time(12, 0)
        )
    
    def test_overlap_partial(self):
        """Частичное пересечение"""
        assert check_time_overlap(
            time(10, 0), time(12, 0),
            time(11, 0), time(13, 0)
        )
    
    def test_overlap_contained(self):
        """Один интервал полностью внутри другого"""
        assert check_time_overlap(
            time(10, 0), time(14, 0),
            time(11, 0), time(12, 0)
        )
    
    def test_overlap_identical(self):
        """Идентичные интервалы"""
        assert check_time_overlap(
            time(10, 0), time(12, 0),
            time(10, 0), time(12, 0)
        )
    
    def test_overlap_start_inside(self):
        """Начало второго интервала внутри первого"""
        assert check_time_overlap(
            time(10, 0), time(12, 0),
            time(11, 30), time(13, 0)
        )
    
    def test_overlap_end_inside(self):
        """Конец первого интервала внутри второго"""
        assert check_time_overlap(
            time(11, 0), time(13, 0),
            time(10, 0), time(12, 0)
        )


class TestBookingValidation:
    """Тесты валидации временных интервалов бронирования"""
    
    def test_valid_booking(self):
        """Валидное бронирование"""
        valid, _ = validate_booking_time(time(10, 0), time(12, 0))
        assert valid
    
    def test_invalid_start_after_end(self):
        """Начало позже окончания"""
        valid, error = validate_booking_time(time(12, 0), time(10, 0))
        assert not valid
        assert "раньше" in error.lower()
    
    def test_invalid_same_time(self):
        """Одинаковое время начала и окончания"""
        valid, error = validate_booking_time(time(10, 0), time(10, 0))
        assert not valid
    
    def test_invalid_too_short(self):
        """Слишком короткий интервал (< 30 минут)"""
        valid, error = validate_booking_time(time(10, 0), time(10, 15))
        assert not valid
        assert "30 минут" in error
    
    def test_invalid_too_long(self):
        """Слишком длинный интервал (> 8 часов)"""
        valid, error = validate_booking_time(time(8, 0), time(17, 0))
        assert not valid
        assert "8 часов" in error
    
    def test_invalid_before_working_hours(self):
        """Бронирование до рабочих часов"""
        valid, error = validate_booking_time(time(7, 0), time(9, 0))
        assert not valid
        assert "08:00" in error
    
    def test_invalid_after_working_hours(self):
        """Бронирование после рабочих часов"""
        valid, error = validate_booking_time(time(21, 0), time(23, 0))
        assert not valid
        assert "22:00" in error
    
    def test_valid_min_duration(self):
        """Минимальная длительность 30 минут"""
        valid, _ = validate_booking_time(time(10, 0), time(10, 30))
        assert valid
    
    def test_valid_max_duration(self):
        """Максимальная длительность 8 часов"""
        valid, _ = validate_booking_time(time(10, 0), time(18, 0))
        assert valid
    
    def test_valid_early_morning(self):
        """Бронирование с начала рабочего дня"""
        valid, _ = validate_booking_time(time(8, 0), time(10, 0))
        assert valid
    
    def test_valid_late_evening(self):
        """Бронирование до конца рабочего дня"""
        valid, _ = validate_booking_time(time(20, 0), time(22, 0))
        assert valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
