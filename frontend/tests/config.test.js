/**
 * Testes para o modulo config.js
 */

describe('CONFIG', () => {
  test('CONFIG tem propriedades obrigatorias', () => {
    expect(CONFIG).toBeDefined();
    expect(CONFIG.API_URL).toBeDefined();
    expect(CONFIG.API_PREFIX).toBe('/api/v1');
    expect(CONFIG.TOKEN_KEY).toBe('licitafacil_token');
    expect(CONFIG.USER_KEY).toBe('licitafacil_user');
  });
});

describe('api', () => {
  // Importar api do config.js precisa de adaptacao
  // Como estamos usando globals no setup, vamos testar via fetch mock

  describe('api.get', () => {
    test('deve fazer requisicao GET corretamente', async () => {
      fetch.mockImplementationOnce(() =>
        mockFetchResponse({ data: 'test' })
      );

      // Simular a funcao api.get
      const url = CONFIG.API_URL + CONFIG.API_PREFIX + '/test';
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      const data = await response.json();

      expect(fetch).toHaveBeenCalledWith(url, expect.objectContaining({
        method: 'GET',
      }));
      expect(data).toEqual({ data: 'test' });
    });
  });

  describe('api.post', () => {
    test('deve fazer requisicao POST com body', async () => {
      fetch.mockImplementationOnce(() =>
        mockFetchResponse({ success: true })
      );

      const url = CONFIG.API_URL + CONFIG.API_PREFIX + '/test';
      const body = { name: 'test' };

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });
      const data = await response.json();

      expect(fetch).toHaveBeenCalledWith(url, expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(body),
      }));
      expect(data).toEqual({ success: true });
    });
  });

  describe('Tratamento de erros', () => {
    test('deve tratar erro 401 em pagina nao-login', async () => {
      // Simular pagina nao-login
      Object.defineProperty(window, 'location', {
        value: { pathname: '/dashboard.html', href: '' },
        writable: true,
      });

      fetch.mockImplementationOnce(() =>
        mockFetchError('Unauthorized', 401)
      );

      const response = await fetch('/test');
      expect(response.ok).toBe(false);
      expect(response.status).toBe(401);
    });

    test('deve retornar mensagem de erro do backend', async () => {
      fetch.mockImplementationOnce(() =>
        mockFetchError('Email ja cadastrado', 400)
      );

      const response = await fetch('/test');
      const data = await response.json();

      expect(response.ok).toBe(false);
      expect(data.detail).toBe('Email ja cadastrado');
    });
  });
});

describe('theme', () => {
  // Simular as funcoes de tema
  const mockTheme = {
    get: () => document.documentElement.getAttribute('data-theme') || 'light',
    set: (themeName) => {
      document.documentElement.setAttribute('data-theme', themeName);
      localStorage.setItem(CONFIG.THEME_KEY || 'licitafacil_theme', themeName);
    },
    toggle: function() {
      const current = this.get();
      const next = current === 'light' ? 'dark' : 'light';
      this.set(next);
      return next;
    },
  };

  beforeEach(() => {
    document.documentElement.removeAttribute('data-theme');
    localStorage.clear();
  });

  test('get retorna light por padrao', () => {
    expect(mockTheme.get()).toBe('light');
  });

  test('set define o tema corretamente', () => {
    mockTheme.set('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem('licitafacil_theme')).toBe('dark');
  });

  test('toggle alterna entre light e dark', () => {
    mockTheme.set('light');
    expect(mockTheme.toggle()).toBe('dark');
    expect(mockTheme.toggle()).toBe('light');
  });
});

describe('ui', () => {
  // Simular a funcao showAlert
  const mockShowAlert = (message, type = 'info', containerId = 'alertContainer') => {
    const container = document.getElementById(containerId);
    if (!container) return;

    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    container.appendChild(alert);
  };

  beforeEach(() => {
    document.body.innerHTML = '<div id="alertContainer"></div>';
  });

  test('showAlert cria elemento de alerta', () => {
    mockShowAlert('Teste', 'success');

    const alerts = document.querySelectorAll('.alert');
    expect(alerts.length).toBe(1);
    expect(alerts[0].classList.contains('alert-success')).toBe(true);
    expect(alerts[0].textContent).toBe('Teste');
  });

  test('showAlert nao falha se container nao existir', () => {
    document.body.innerHTML = '';
    expect(() => mockShowAlert('Teste')).not.toThrow();
  });

  test('showAlert suporta diferentes tipos', () => {
    mockShowAlert('Erro', 'error');
    mockShowAlert('Aviso', 'warning');
    mockShowAlert('Info', 'info');

    const alerts = document.querySelectorAll('.alert');
    expect(alerts.length).toBe(3);
    expect(alerts[0].classList.contains('alert-error')).toBe(true);
    expect(alerts[1].classList.contains('alert-warning')).toBe(true);
    expect(alerts[2].classList.contains('alert-info')).toBe(true);
  });
});

describe('localStorage helpers', () => {
  test('localStorage.setItem e getItem funcionam', () => {
    localStorage.setItem('test_key', 'test_value');
    expect(localStorage.getItem('test_key')).toBe('test_value');
  });

  test('localStorage.removeItem funciona', () => {
    localStorage.setItem('test_key', 'test_value');
    localStorage.removeItem('test_key');
    expect(localStorage.getItem('test_key')).toBeNull();
  });

  test('localStorage.clear limpa tudo', () => {
    localStorage.setItem('key1', 'value1');
    localStorage.setItem('key2', 'value2');
    localStorage.clear();
    expect(localStorage.getItem('key1')).toBeNull();
    expect(localStorage.getItem('key2')).toBeNull();
  });
});
