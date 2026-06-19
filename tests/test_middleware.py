import pytest
from django.test import RequestFactory, override_settings

from nocturne.middleware import NocturneMiddleware
from nocturne.models import LogEntry


@pytest.fixture
def middleware():
    def get_response(request):
        from django.http import HttpResponse
        return HttpResponse("ok", status=200)
    return NocturneMiddleware(get_response)


@pytest.mark.django_db
def test_middleware_records_info_request(middleware):
    factory = RequestFactory()
    request = factory.get("/ping/")
    middleware(request)
    assert LogEntry.objects.filter(request_path="/ping/", level="INFO").exists()


@pytest.mark.django_db
def test_middleware_records_404_as_warning(middleware):
    def get_response(request):
        from django.http import HttpResponse
        return HttpResponse("not found", status=404)
    m = NocturneMiddleware(get_response)
    factory = RequestFactory()
    request = factory.get("/missing/")
    m(request)
    assert LogEntry.objects.filter(request_path="/missing/", level="WARNING").exists()


@pytest.mark.django_db
@override_settings(NOCTURNE={"EXCLUDE_PATHS": ["/ping/"], "SERVICE_NAME": "test"})
def test_middleware_skips_excluded_paths():
    def get_response(request):
        from django.http import HttpResponse
        return HttpResponse("ok")
    m = NocturneMiddleware(get_response)
    factory = RequestFactory()
    request = factory.get("/ping/")
    m(request)
    assert not LogEntry.objects.filter(request_path="/ping/").exists()


@pytest.mark.django_db
def test_middleware_captures_exception():
    def get_response(request):
        from django.http import HttpResponse
        return HttpResponse("error", status=500)

    def exc_raiser(request):
        raise ValueError("test error")

    m = NocturneMiddleware(get_response)
    factory = RequestFactory()
    request = factory.get("/error/")
    # Simulate process_exception being called first
    try:
        exc_raiser(request)
    except ValueError as e:
        m.process_exception(request, e)
    m(request)
    entry = LogEntry.objects.filter(request_path="/error/").first()
    assert entry is not None
    assert entry.exception_type == "ValueError"
