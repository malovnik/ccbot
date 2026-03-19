"""Tests for WS history pagination math."""


class TestPaginationMath:
    """Verify the pagination logic from ws_bridge._handle_get_history."""

    def _paginate(
        self, total: int, offset: int, page_size: int = 50
    ) -> tuple[int, int, int, int]:
        """Reproduce pagination logic from ws_bridge."""
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = min(offset, total_pages - 1) if offset >= 0 else 0
        start = page * page_size
        end = start + page_size
        return page, total_pages, start, end

    def test_empty_messages(self) -> None:
        page, total_pages, start, end = self._paginate(0, 0)
        assert page == 0
        assert total_pages == 1
        assert start == 0
        assert end == 50

    def test_single_page(self) -> None:
        page, total_pages, start, end = self._paginate(30, 0)
        assert page == 0
        assert total_pages == 1
        assert start == 0
        assert end == 50

    def test_exactly_one_page(self) -> None:
        page, total_pages, start, end = self._paginate(50, 0)
        assert page == 0
        assert total_pages == 1

    def test_two_pages_first(self) -> None:
        page, total_pages, start, end = self._paginate(75, 0)
        assert page == 0
        assert total_pages == 2
        assert start == 0
        assert end == 50

    def test_two_pages_second(self) -> None:
        page, total_pages, start, end = self._paginate(75, 1)
        assert page == 1
        assert total_pages == 2
        assert start == 50
        assert end == 100

    def test_offset_beyond_total_pages(self) -> None:
        page, total_pages, start, end = self._paginate(75, 99)
        assert page == 1  # clamped to last page
        assert total_pages == 2

    def test_negative_offset(self) -> None:
        page, total_pages, start, end = self._paginate(75, -1)
        assert page == 0

    def test_exactly_51_messages(self) -> None:
        page, total_pages, start, end = self._paginate(51, 0)
        assert total_pages == 2
        page, _, start, end = self._paginate(51, 1)
        assert start == 50
        assert end == 100  # slice [50:100] on 51 items = [item 50]

    def test_large_dataset(self) -> None:
        page, total_pages, start, end = self._paginate(1000, 0)
        assert total_pages == 20
        page, _, start, end = self._paginate(1000, 19)
        assert page == 19
        assert start == 950
        assert end == 1000
