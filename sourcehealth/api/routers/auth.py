"""Auth HTTP endpoints."""

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse, Response

from ..dependencies import check_origin, require_user
from ..schemas import UserDTO

router = APIRouter()


def cookie(request, response, name, token, max_age):
    response.set_cookie(name, token, max_age=max_age, secure=request.app.state.settings.cookie_secure, httponly=True,
                        samesite="lax", path="/")


@router.get("/api/v1/auth/yandex/login", response_class=RedirectResponse)
def login(request: Request):
    url, token = request.app.state.auth.login()
    response = RedirectResponse(url, status_code=302)
    cookie(request, response, "sh_oauth", token, 600)
    return response


@router.get("/api/v1/auth/yandex/callback", response_class=RedirectResponse)
def callback(request: Request, state: str = Query(max_length=256), code: str = Query(max_length=2048)):
    token = request.app.state.auth.callback(browser_token=request.cookies.get("sh_oauth", ""), state=state, code=code)
    request.app.state.auth.logout(request.cookies.get("sh_session"))
    response = RedirectResponse("/auth/callback", status_code=303)
    response.delete_cookie("sh_oauth", path="/")
    cookie(request, response, "sh_session", token, request.app.state.settings.session_ttl)
    return response


@router.post("/api/v1/auth/logout", status_code=204)
def logout(request: Request):
    check_origin(request)
    request.app.state.auth.logout(request.cookies.get("sh_session"))
    response = Response(status_code=204)
    response.delete_cookie("sh_session", path="/")
    return response


@router.get("/api/v1/me", response_model=UserDTO)
def me(request: Request):
    return require_user(request)
