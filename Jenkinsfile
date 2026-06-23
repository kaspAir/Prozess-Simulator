// Prozess-Simulator (ProS) CI/CD-Pipeline
//
// Branch-Flow:  dev → test → integration → main
//
// Pipeline-Jobs (Job-Name muss den Branch enthalten):
//   prozess-simulator dev          → nur Tests (kein Deploy)
//   prozess-simulator test         → Tests + Deploy test         (Port 8011, test.ditwi.ch)
//   prozess-simulator integration  → Tests + Deploy integration  (Port 8012, int.ditwi.ch)
//   prozess-simulator main         → Tests + Deploy prod          (Port 8010, ditwi.ch)
//
// Voraussetzungen Jenkins:
//   - SSH-Credential 'hermespia-deploy' (privater Key fuer den Deploy-User)
//   - Docker + Docker-Pipeline-Plugin (fuer die Test-Stage im Container)
//
// Voraussetzungen Server (siehe deploy/SERVER_SETUP.md):
//   - App-Verzeichnisse ~/prozess-simulator[-test|-int] mit je .env + data/ + logs/
//   - Python 3 vorhanden (venv wird pro App-Verzeichnis automatisch erstellt)

pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 20, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    environment {
        DEPLOY_HOST = 'u7031y_kaspar@83.228.238.194'
        REPO_URL    = 'https://github.com/kaspAir/Prozess-Simulator'
    }

    stages {

        stage('Tests') {
            steps {
                script {
                    docker.image('python:3.12-slim').inside('-u root') {
                        sh '''
                            python --version
                            pip install --no-cache-dir -r tests/requirements.txt
                            pytest tests/ -v --junitxml=reports/junit.xml
                        '''
                    }
                }
            }
            post {
                always {
                    junit 'reports/junit.xml'
                }
            }
        }

        stage('Deploy prod') {
            when { expression { env.JOB_NAME.contains('main') } }
            steps {
                sshagent(credentials: ['hermespia-deploy']) {
                    sh """
                        ssh -o StrictHostKeyChecking=no ${DEPLOY_HOST} '
                            APP_DIR=\$HOME/prozess-simulator
                            mkdir -p "\$APP_DIR/data" "\$APP_DIR/logs" \$HOME/tmp
                            cd "\$APP_DIR"
                            if [ ! -d .git ]; then git init -q && git remote add origin ${REPO_URL}; fi
                            git remote set-url origin ${REPO_URL}
                            git fetch origin
                            git reset --hard origin/main
                            [ -d .venv ] || python3 -m venv .venv
                            . .venv/bin/activate
                            pip install -r requirements.txt -q
                            set -a; [ -f .env ] && . ./.env; set +a
                            [ -f data/prozess_simulator.db ] || python init_db.py
                            PID_FILE=\$HOME/tmp/gunicorn-pros-prod.pid
                            [ -f "\$PID_FILE" ] && kill \$(cat "\$PID_FILE") 2>/dev/null || true
                            sleep 1
                            nohup .venv/bin/gunicorn run:app \\
                                --bind 127.0.0.1:8010 --workers 2 --timeout 120 \\
                                --access-logfile logs/access.log \\
                                --error-logfile logs/error.log > /dev/null 2>&1 &
                            echo \$! > "\$PID_FILE"
                            sleep 2 && curl -sf http://127.0.0.1:8010 > /dev/null && echo "OK: prod laeuft"
                        '
                    """
                }
            }
        }

        stage('Deploy integration') {
            when { expression { env.JOB_NAME.contains('integration') } }
            steps {
                sshagent(credentials: ['hermespia-deploy']) {
                    sh """
                        ssh -o StrictHostKeyChecking=no ${DEPLOY_HOST} '
                            APP_DIR=\$HOME/prozess-simulator-int
                            mkdir -p "\$APP_DIR/data" "\$APP_DIR/logs" \$HOME/tmp
                            cd "\$APP_DIR"
                            if [ ! -d .git ]; then git init -q && git remote add origin ${REPO_URL}; fi
                            git remote set-url origin ${REPO_URL}
                            git fetch origin
                            git reset --hard origin/integration
                            [ -d .venv ] || python3 -m venv .venv
                            . .venv/bin/activate
                            pip install -r requirements.txt -q
                            set -a; [ -f .env ] && . ./.env; set +a
                            [ -f data/prozess_simulator.db ] || python init_db.py
                            PID_FILE=\$HOME/tmp/gunicorn-pros-int.pid
                            [ -f "\$PID_FILE" ] && kill \$(cat "\$PID_FILE") 2>/dev/null || true
                            sleep 1
                            nohup .venv/bin/gunicorn run:app \\
                                --bind 127.0.0.1:8012 --workers 1 --timeout 120 \\
                                --access-logfile logs/access.log \\
                                --error-logfile logs/error.log > /dev/null 2>&1 &
                            echo \$! > "\$PID_FILE"
                            sleep 2 && curl -sf http://127.0.0.1:8012 > /dev/null && echo "OK: integration laeuft"
                        '
                    """
                }
            }
        }

        stage('Deploy test') {
            when { expression { env.JOB_NAME.contains('test') } }
            steps {
                sshagent(credentials: ['hermespia-deploy']) {
                    sh """
                        ssh -o StrictHostKeyChecking=no ${DEPLOY_HOST} '
                            APP_DIR=\$HOME/prozess-simulator-test
                            mkdir -p "\$APP_DIR/data" "\$APP_DIR/logs" \$HOME/tmp
                            cd "\$APP_DIR"
                            if [ ! -d .git ]; then git init -q && git remote add origin ${REPO_URL}; fi
                            git remote set-url origin ${REPO_URL}
                            git fetch origin
                            git reset --hard origin/test
                            [ -d .venv ] || python3 -m venv .venv
                            . .venv/bin/activate
                            pip install -r requirements.txt -q
                            set -a; [ -f .env ] && . ./.env; set +a
                            [ -f data/prozess_simulator.db ] || python init_db.py
                            PID_FILE=\$HOME/tmp/gunicorn-pros-test.pid
                            [ -f "\$PID_FILE" ] && kill \$(cat "\$PID_FILE") 2>/dev/null || true
                            sleep 1
                            nohup .venv/bin/gunicorn run:app \\
                                --bind 127.0.0.1:8011 --workers 1 --timeout 120 \\
                                --access-logfile logs/access.log \\
                                --error-logfile logs/error.log > /dev/null 2>&1 &
                            echo \$! > "\$PID_FILE"
                            sleep 2 && curl -sf http://127.0.0.1:8011 > /dev/null && echo "OK: test laeuft"
                        '
                    """
                }
            }
        }

    }

    post {
        success { echo 'Pipeline gruen.' }
        failure { echo 'Pipeline rot – siehe Stage-Logs und Testbericht.' }
    }
}
