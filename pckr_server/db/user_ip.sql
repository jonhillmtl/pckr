CREATE TABLE user_ip (
    public_key      VARCHAR NOT NULL,
    ip              CHAR(20),
    port            int NOT NULL,
    phone_number    VARCHAR NOT NULL,
    updated_at      TIMESTAMP NOT NULL,
    login_token     VARCHAR NOT NULL
);