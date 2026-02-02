/**
 * Setup global para testes Jest do frontend LicitaFacil.
 *
 * Configura mocks globais necessarios para testes de funcoes
 * que dependem de APIs do navegador.
 */

// Mock do localStorage
const localStorageMock = {
  store: {},
  getItem: jest.fn((key) => localStorageMock.store[key] || null),
  setItem: jest.fn((key, value) => {
    localStorageMock.store[key] = String(value);
  }),
  removeItem: jest.fn((key) => {
    delete localStorageMock.store[key];
  }),
  clear: jest.fn(() => {
    localStorageMock.store = {};
  }),
};

Object.defineProperty(global, 'localStorage', {
  value: localStorageMock,
});

// Mock do fetch
global.fetch = jest.fn();

// Mock do console para testes silenciosos
// Descomente para suprimir logs durante testes
// global.console = {
//   ...console,
//   log: jest.fn(),
//   error: jest.fn(),
//   warn: jest.fn(),
// };

// Mock do alert/confirm
global.alert = jest.fn();
global.confirm = jest.fn(() => true);

// Mock basico do DOM
document.body.innerHTML = '<div id="app"></div>';

// Reset mocks antes de cada teste
beforeEach(() => {
  jest.clearAllMocks();
  localStorageMock.clear();
  localStorageMock.store = {};
  fetch.mockReset();
});

// CONFIG global (simulando o que seria carregado do config.js)
global.CONFIG = {
  API_URL: 'http://localhost:8000',
  API_PREFIX: '/api/v1',
  TOKEN_KEY: 'licitafacil_token',
  USER_KEY: 'licitafacil_user',
};

// Helper para criar resposta mock do fetch
global.mockFetchResponse = (data, ok = true, status = 200) => {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  });
};

// Helper para criar resposta de erro do fetch
global.mockFetchError = (message, status = 400) => {
  return Promise.resolve({
    ok: false,
    status,
    json: () => Promise.resolve({ detail: message }),
    text: () => Promise.resolve(JSON.stringify({ detail: message })),
  });
};
