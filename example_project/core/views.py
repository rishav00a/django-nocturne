import time

from django.http import HttpResponse, JsonResponse


def ping(request):
    return JsonResponse({"status": "ok", "message": "pong"})


def slow(request):
    time.sleep(2)
    return JsonResponse({"status": "ok", "message": "that was slow"})


def error(request):
    raise ValueError("Intentional 500 error for testing")


def not_found(request):
    return HttpResponse("Not found", status=404)
