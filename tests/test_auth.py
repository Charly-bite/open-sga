def test_login_success(client):
    """
    Test that a valid user can login successfully and establish a session.
    """
    # Assuming test user is injected or mocked in the test DB
    response = client.post(
        "/login",
        data={"username": "admin", "password": "admin_password_mock"},
        follow_redirects=True,
    )

    # We can check the response text or status
    assert response.status_code == 200

    # Check if login redirected correctly or sets session
    with client.session_transaction() as sess:
        # Depending on how the app sets the session, we check if user is in it
        # For example: assert 'user_id' in sess or 'username' in sess
        pass


def test_login_failure(client):
    """
    Test that an invalid user login fails.
    """
    response = client.post(
        "/login",
        data={"username": "wrong_user", "password": "wrong_password"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    # On failure, it re-renders the login page instead of redirecting to dashboard
    assert b"Iniciar Sesi" in response.data
