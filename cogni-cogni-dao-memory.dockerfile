# syntax=docker/dockerfile:1.3-labs
FROM ubuntu:20.04
WORKDIR /
RUN apt update &&     apt upgrade -y &&     apt install -y curl     && curl -L https://github.com/dolthub/dolt/releases/latest/download/install.sh | bash

ENV HOST="0.0.0.0"
ENV PORT=3306
ENV DOLT_ROOT_PATH="/.dolt"
ENV DATABASE_REMOTE="https://doltremoteapi.dolthub.com/cogni/cogni-dao-memory"
ENV DATABASE_NAME=cogni-dao-memory
ENV DOLTHUB_USER=cogni
ENV DOLTHUB_EMAIL=steward@cognidao.org
ENV DATA_DIR="/dolthub-dbs/cogni/$DATABASE_NAME"

EXPOSE 3306
VOLUME [ "/dolthub-dbs" ]

RUN cat <<EOF > /entrypoint.sh
#!/bin/bash
set -eo pipefail

# fail a step and print the message
_fail() {
  local message="\$1"
  echo "\$message"
  exit 1;
}

# check a single environment variable value
_check_var() {
  local key="\$1"
  local val="\$2"

  if [ "\$val" == "" ]; then
    _fail "Must set \$key"
  fi
}

# check that expected environment variables are defined
check_env_vars() {
  echo "Checking Environment Variables..."
  _check_var "HOST" "\$HOST"
  _check_var "PORT" "\$PORT"
  _check_var "DOLT_ROOT_PATH" "\$DOLT_ROOT_PATH"
  _check_var "DATABASE_REMOTE" "\$DATABASE_REMOTE"
  _check_var "DATABASE_NAME" "\$DATABASE_NAME"
  _check_var "DOLTHUB_USER" "\$DOLTHUB_USER"
  _check_var "DOLTHUB_EMAIL" "\$DOLTHUB_EMAIL"
  _check_var "DATA_DIR" "\$DATA_DIR"
}

# create all dirs in path
_create_dir() {
  local path="\$1"
  mkdir -p "\$path"
}

# create required directories
create_directories() {
  echo "Creating Directories..."
  _create_dir "/dolthub-dbs/cogni"
}

configure_dolt_server() {
  echo "Configuring Dolt Server..."
  local dolt_bin=\$(which dolt)
  if [ ! -x "\$dolt_bin" ]; then
      _fail "dolt not found on PATH"
  fi

  # required for `dolt creds import`
  dolt config --global --add user.name "\$DOLTHUB_USER"
  dolt config --global --add user.email "\$DOLTHUB_EMAIL"
}

# setup creds for the dolt server so it can clone
authenticate_dolt_server() {
  if [ -n "\$CREDS_KEY" ] && [ -n "\$CREDS_VALUE" ]; then
    echo "Authenticating Dolt Server..."

    local creds_path="\$DOLT_ROOT_PATH/creds"
    _create_dir "\$creds_path"

    echo "\$CREDS_VALUE" > "\$creds_path/\$CREDS_KEY".jwk
    dolt creds import "\$creds_path/\$CREDS_KEY".jwk
    dolt creds use \$CREDS_KEY
  fi
}

# clones the database if it's not found
clone_database() {
  if [ -d "\$DATA_DIR" ]
  then
    echo "Database found at \$DATA_DIR, skipping clone..."
  else
  echo "Cloning database..."
    (
      local wd=\$(pwd)
      cd "/dolthub-dbs/cogni"
      dolt clone "\$DATABASE_REMOTE"
      cd "\$DATA_DIR"
      dolt sql -q "show databases"
      cd "\$wd"
    )
  fi
}

update_database_permissions() {
  echo "Updating database permissions..."
}

finalize_setup() {
  # echo "Finalizing database setup..."
  local replaced_name=\$(echo "\${DATABASE_NAME//-/\$'_'}")
  echo "*****"
  echo "Client must run 'USE \$replaced_name;' to start accessing the data."
  echo "*****"
}

_main() {
  check_env_vars
  create_directories
  configure_dolt_server
  authenticate_dolt_server
  clone_database
  update_database_permissions
  finalize_setup

  cd "\$DATA_DIR"
  exec "\$@"
}

_main "\$@"
  
EOF

RUN chmod +x /entrypoint.sh
ENTRYPOINT [ "/entrypoint.sh" ]

WORKDIR /dolthub-dbs/cogni
CMD [ "dolt", "sql-server", "-l=trace", "--host=0.0.0.0", "--port=3306"]
