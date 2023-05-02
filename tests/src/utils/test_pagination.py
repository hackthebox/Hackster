import pytest

from src.utils.pagination import ImagePaginator, LinePaginator


class TestLinePaginator:
    """Test the `LinePaginator` class."""

    def test_add_line_works_on_small_lines(self):
        """`add_line` should allow small lines to be added."""
        paginator = LinePaginator(prefix="", suffix="", max_size=30)

        paginator.add_line('x' * (paginator.max_size - 2))
        assert len(paginator._pages) == 0  # Note that the page isn't added to _pages until it's full.

    def test_add_line_raises_on_long_line(self):
        """If the size of a line exceeds `max_size` a RuntimeError should occur."""
        paginator = LinePaginator(prefix="", suffix="", max_size=30)

        with pytest.raises(RuntimeError):
            paginator.add_line("x" * paginator.max_size)

    def test_add_line_works_on_long_lines(self):
        """After additional lines after `max_size` is exceeded should go on the next page."""
        paginator = LinePaginator(prefix="", suffix="", max_size=30)

        paginator.add_line('x' * (paginator.max_size - 2))
        assert len(paginator._pages) == 0

        # Any additional lines should start a new page after `max_size` is exceeded.
        paginator.add_line('x')
        assert len(paginator._pages) == 1

    def test_add_line_max_lines(self):
        """After additional lines after `max_size` is exceeded should go on the next page."""
        paginator = LinePaginator(prefix="", suffix="", max_size=30, max_lines=2)

        paginator.add_line('x')
        paginator.add_line('x')
        assert len(paginator._pages) == 0

        # Any additional lines should start a new page after `max_lines` is exceeded.
        paginator.add_line('x')
        assert len(paginator._pages) == 1

    def test_add_line_adds_empty_lines(self):
        """Using the `empty` argument should add an empty line."""
        paginator = LinePaginator(prefix="", suffix="", max_size=30)

        paginator.add_line('x')
        assert paginator._count == 3

        # Using `empty` should add 2 to the count instead of 1.
        paginator.add_line('x', empty=True)
        assert paginator._count == 6


class TestImagePaginator:
    """Test the `ImagePaginator` class."""

    def test_add_line_create_new_page(self):
        """`add_line` should add each line to a page."""
        paginator = ImagePaginator(prefix="", suffix="")

        paginator.add_line('x')
        assert len(paginator._pages) == 1

        paginator.add_line()
        assert len(paginator._pages) == 2

    def test_add_image(self):
        """Test the `add_image` function."""
        paginator = ImagePaginator(prefix="", suffix="")

        paginator.add_image("url")
        assert len(paginator.images) == 1
