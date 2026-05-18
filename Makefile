.PHONY: venv install setup ollama-up ollama-down ollama-pull run clean clean-all help all

VENV        = .venv
PYTHON      = $(VENV)/bin/python
PIP         = $(VENV)/bin/pip
OLLAMA_MODEL     ?= llama3.2
OLLAMA_CONTAINER  = responsable-ai-ollama-1

help:
	@echo ""
	@echo "Responsible AI — comandos disponíveis:"
	@echo ""
	@echo "  make venv          Cria o ambiente virtual (.venv)"
	@echo "  make install       Instala dependências Python no venv"
	@echo "  make setup         Instala tudo (deps + modelos spaCy + Detoxify)"
	@echo "  make ollama-up     Sobe o Ollama via Docker Compose"
	@echo "  make ollama-pull   Baixa o modelo $(OLLAMA_MODEL) no Ollama"
	@echo "  make ollama-down   Para e remove o container do Ollama"
	@echo "  make run           Inicia a aplicação Gradio"
	@echo "  make all           setup + ollama-up + ollama-pull + run"
	@echo "  make clean         Remove venv e cache Python"
	@echo "  make clean-all     Remove tudo: venv, cache e volumes Docker"
	@echo ""

$(VENV)/bin/activate:
	python3 -m venv $(VENV)

venv: $(VENV)/bin/activate

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

setup: install
	$(PYTHON) -m spacy download en_core_web_lg
	$(PYTHON) -c "from detoxify import Detoxify; Detoxify('original'); print('Detoxify OK')"

ollama-up:
	docker compose up -d
	@echo "Aguardando Ollama iniciar..."
	@until docker exec $(OLLAMA_CONTAINER) ollama list > /dev/null 2>&1; do sleep 1; done
	@echo "Ollama pronto."

ollama-pull: ollama-up
	docker exec $(OLLAMA_CONTAINER) ollama pull $(OLLAMA_MODEL)

ollama-down:
	docker compose down

run: venv
	$(PYTHON) app.py

all: setup ollama-pull run

clean:
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc" -delete 2>/dev/null; true

clean-all: ollama-down clean
	docker compose down --volumes --remove-orphans
	@echo "Limpeza completa concluída."
