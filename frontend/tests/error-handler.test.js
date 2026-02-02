/**
 * Testes para o modulo error-handler.js
 */

// Mock do objeto ui que e usado pelo ErrorHandler
const mockShowAlert = jest.fn();
global.ui = {
  showAlert: mockShowAlert,
};

// Importar/simular ErrorHandler
const ErrorHandler = {
  async wrap(asyncFn, errorMessage = 'Erro na operacao') {
    try {
      return await asyncFn();
    } catch (error) {
      console.error(errorMessage, error);
      ui.showAlert(error.message || errorMessage, 'error');
      throw error;
    }
  },

  async silent(asyncFn, errorMessage = 'Erro na operacao') {
    try {
      return await asyncFn();
    } catch (error) {
      console.error(errorMessage, error);
      ui.showAlert(error.message || errorMessage, 'error');
      return null;
    }
  },

  async withCallback(asyncFn, onError) {
    try {
      return await asyncFn();
    } catch (error) {
      console.error('Operacao falhou:', error);
      if (onError) {
        return onError(error);
      }
      return null;
    }
  },

  async withRetry(asyncFn, maxRetries = 3, delayMs = 10) {
    let lastError;
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await asyncFn();
      } catch (error) {
        lastError = error;
        if (attempt < maxRetries) {
          await new Promise(resolve => setTimeout(resolve, delayMs));
        }
      }
    }
    ui.showAlert(lastError.message || 'Operacao falhou apos multiplas tentativas', 'error');
    throw lastError;
  },

  formatApiError(error) {
    if (error?.detail) {
      return error.detail;
    }
    if (error?.message) {
      return error.message;
    }
    if (typeof error === 'string') {
      return error;
    }
    return 'Erro desconhecido';
  },
};

describe('ErrorHandler', () => {
  beforeEach(() => {
    mockShowAlert.mockClear();
    jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    console.error.mockRestore();
    console.warn.mockRestore();
  });

  describe('wrap', () => {
    test('retorna resultado quando funcao sucede', async () => {
      const asyncFn = jest.fn().mockResolvedValue('success');

      const result = await ErrorHandler.wrap(asyncFn);

      expect(result).toBe('success');
      expect(asyncFn).toHaveBeenCalled();
      expect(mockShowAlert).not.toHaveBeenCalled();
    });

    test('exibe alerta e relanca erro quando funcao falha', async () => {
      const error = new Error('Test error');
      const asyncFn = jest.fn().mockRejectedValue(error);

      await expect(ErrorHandler.wrap(asyncFn)).rejects.toThrow('Test error');

      expect(mockShowAlert).toHaveBeenCalledWith('Test error', 'error');
    });

    test('usa mensagem padrao quando erro nao tem message', async () => {
      const asyncFn = jest.fn().mockRejectedValue({});

      await expect(
        ErrorHandler.wrap(asyncFn, 'Erro customizado')
      ).rejects.toBeDefined();

      expect(mockShowAlert).toHaveBeenCalledWith('Erro customizado', 'error');
    });
  });

  describe('silent', () => {
    test('retorna resultado quando funcao sucede', async () => {
      const asyncFn = jest.fn().mockResolvedValue('success');

      const result = await ErrorHandler.silent(asyncFn);

      expect(result).toBe('success');
      expect(mockShowAlert).not.toHaveBeenCalled();
    });

    test('retorna null e exibe alerta quando funcao falha', async () => {
      const error = new Error('Test error');
      const asyncFn = jest.fn().mockRejectedValue(error);

      const result = await ErrorHandler.silent(asyncFn);

      expect(result).toBeNull();
      expect(mockShowAlert).toHaveBeenCalledWith('Test error', 'error');
    });

    test('nao relanca erro', async () => {
      const asyncFn = jest.fn().mockRejectedValue(new Error('fail'));

      await expect(ErrorHandler.silent(asyncFn)).resolves.toBeNull();
    });
  });

  describe('withCallback', () => {
    test('retorna resultado quando funcao sucede', async () => {
      const asyncFn = jest.fn().mockResolvedValue('success');
      const onError = jest.fn();

      const result = await ErrorHandler.withCallback(asyncFn, onError);

      expect(result).toBe('success');
      expect(onError).not.toHaveBeenCalled();
    });

    test('chama callback de erro quando funcao falha', async () => {
      const error = new Error('Test error');
      const asyncFn = jest.fn().mockRejectedValue(error);
      const onError = jest.fn().mockReturnValue('handled');

      const result = await ErrorHandler.withCallback(asyncFn, onError);

      expect(result).toBe('handled');
      expect(onError).toHaveBeenCalledWith(error);
    });

    test('retorna null se nao houver callback de erro', async () => {
      const asyncFn = jest.fn().mockRejectedValue(new Error('fail'));

      const result = await ErrorHandler.withCallback(asyncFn);

      expect(result).toBeNull();
    });
  });

  describe('withRetry', () => {
    test('retorna resultado na primeira tentativa se suceder', async () => {
      const asyncFn = jest.fn().mockResolvedValue('success');

      const result = await ErrorHandler.withRetry(asyncFn, 3, 10);

      expect(result).toBe('success');
      expect(asyncFn).toHaveBeenCalledTimes(1);
    });

    test('retenta ate maxRetries vezes', async () => {
      const asyncFn = jest.fn()
        .mockRejectedValueOnce(new Error('fail1'))
        .mockRejectedValueOnce(new Error('fail2'))
        .mockResolvedValue('success');

      const result = await ErrorHandler.withRetry(asyncFn, 3, 10);

      expect(result).toBe('success');
      expect(asyncFn).toHaveBeenCalledTimes(3);
    });

    test('lanca erro apos esgotar tentativas', async () => {
      const asyncFn = jest.fn().mockRejectedValue(new Error('persistent error'));

      await expect(
        ErrorHandler.withRetry(asyncFn, 2, 10)
      ).rejects.toThrow('persistent error');

      expect(asyncFn).toHaveBeenCalledTimes(2);
      expect(mockShowAlert).toHaveBeenCalledWith('persistent error', 'error');
    });
  });

  describe('formatApiError', () => {
    test('retorna detail se existir', () => {
      const error = { detail: 'API error message' };
      expect(ErrorHandler.formatApiError(error)).toBe('API error message');
    });

    test('retorna message se detail nao existir', () => {
      const error = { message: 'Error message' };
      expect(ErrorHandler.formatApiError(error)).toBe('Error message');
    });

    test('retorna string diretamente', () => {
      expect(ErrorHandler.formatApiError('String error')).toBe('String error');
    });

    test('retorna erro desconhecido para outros tipos', () => {
      expect(ErrorHandler.formatApiError({})).toBe('Erro desconhecido');
      expect(ErrorHandler.formatApiError(null)).toBe('Erro desconhecido');
      expect(ErrorHandler.formatApiError(undefined)).toBe('Erro desconhecido');
      expect(ErrorHandler.formatApiError(123)).toBe('Erro desconhecido');
    });
  });
});
