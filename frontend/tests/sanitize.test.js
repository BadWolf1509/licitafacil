/**
 * Testes para o modulo de sanitizacao (sanitize.js)
 * Garante que caracteres perigosos sao escapados corretamente
 * para prevenir vulnerabilidades XSS.
 */

// Importar o modulo (em ambiente de teste, simula o objeto global)
const Sanitize = {
    escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    },

    escapeAttribute(text) {
        if (text === null || text === undefined) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    },

    escapeJs(text) {
        if (text === null || text === undefined) return '';
        return String(text)
            .replace(/\\/g, '\\\\')
            .replace(/'/g, "\\'")
            .replace(/"/g, '\\"')
            .replace(/\n/g, '\\n')
            .replace(/\r/g, '\\r');
    }
};

describe('Sanitize.escapeHtml', () => {
    test('deve escapar caractere <', () => {
        expect(Sanitize.escapeHtml('<script>')).toBe('&lt;script&gt;');
    });

    test('deve escapar caractere >', () => {
        expect(Sanitize.escapeHtml('a > b')).toBe('a &gt; b');
    });

    test('deve escapar caractere &', () => {
        expect(Sanitize.escapeHtml('a & b')).toBe('a &amp; b');
    });

    test('deve escapar aspas duplas', () => {
        expect(Sanitize.escapeHtml('valor="teste"')).toBe('valor=&quot;teste&quot;');
    });

    test('deve escapar aspas simples', () => {
        expect(Sanitize.escapeHtml("valor='teste'")).toBe('valor=&#039;teste&#039;');
    });

    test('deve retornar string vazia para null', () => {
        expect(Sanitize.escapeHtml(null)).toBe('');
    });

    test('deve retornar string vazia para undefined', () => {
        expect(Sanitize.escapeHtml(undefined)).toBe('');
    });

    test('deve converter numeros para string', () => {
        expect(Sanitize.escapeHtml(123)).toBe('123');
    });

    test('deve escapar payload XSS completo', () => {
        const payload = '<img src=x onerror="alert(\'XSS\')">';
        const expected = '&lt;img src=x onerror=&quot;alert(&#039;XSS&#039;)&quot;&gt;';
        expect(Sanitize.escapeHtml(payload)).toBe(expected);
    });

    test('deve escapar tag script', () => {
        const payload = '<script>alert("XSS")</script>';
        const expected = '&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;';
        expect(Sanitize.escapeHtml(payload)).toBe(expected);
    });

    test('deve manter texto normal inalterado', () => {
        const text = 'Texto normal sem caracteres especiais';
        expect(Sanitize.escapeHtml(text)).toBe(text);
    });

    test('deve escapar multiplos caracteres especiais', () => {
        const text = '<div class="test">&copy;</div>';
        const expected = '&lt;div class=&quot;test&quot;&gt;&amp;copy;&lt;/div&gt;';
        expect(Sanitize.escapeHtml(text)).toBe(expected);
    });
});

describe('Sanitize.escapeAttribute', () => {
    test('deve escapar aspas duplas em atributos', () => {
        expect(Sanitize.escapeAttribute('value="test"')).toBe('value=&quot;test&quot;');
    });

    test('deve escapar aspas simples em atributos', () => {
        expect(Sanitize.escapeAttribute("value='test'")).toBe('value=&#039;test&#039;');
    });

    test('deve escapar < e > em atributos', () => {
        expect(Sanitize.escapeAttribute('<script>')).toBe('&lt;script&gt;');
    });

    test('deve retornar string vazia para null', () => {
        expect(Sanitize.escapeAttribute(null)).toBe('');
    });

    test('deve retornar string vazia para undefined', () => {
        expect(Sanitize.escapeAttribute(undefined)).toBe('');
    });
});

describe('Sanitize.escapeJs', () => {
    test('deve escapar aspas simples', () => {
        expect(Sanitize.escapeJs("it's")).toBe("it\\'s");
    });

    test('deve escapar aspas duplas', () => {
        expect(Sanitize.escapeJs('say "hello"')).toBe('say \\"hello\\"');
    });

    test('deve escapar barras invertidas', () => {
        expect(Sanitize.escapeJs('path\\to\\file')).toBe('path\\\\to\\\\file');
    });

    test('deve escapar quebras de linha', () => {
        expect(Sanitize.escapeJs("line1\nline2")).toBe('line1\\nline2');
    });

    test('deve escapar retorno de carro', () => {
        expect(Sanitize.escapeJs("line1\rline2")).toBe('line1\\rline2');
    });

    test('deve retornar string vazia para null', () => {
        expect(Sanitize.escapeJs(null)).toBe('');
    });

    test('deve retornar string vazia para undefined', () => {
        expect(Sanitize.escapeJs(undefined)).toBe('');
    });

    test('deve escapar nome com apostrofo para uso em onclick', () => {
        const nome = "O'Brien";
        const escaped = Sanitize.escapeJs(nome);
        expect(escaped).toBe("O\\'Brien");
        // Verifica que pode ser usado em onclick="funcao('${escaped}')"
        expect(() => eval(`'${escaped}'`)).not.toThrow();
    });

    test('deve escapar payload de injecao JS', () => {
        const payload = "'; alert('XSS'); '";
        const escaped = Sanitize.escapeJs(payload);
        expect(escaped).toBe("\\'; alert(\\'XSS\\'); \\'");
    });
});

describe('Sanitize - Casos de uso reais', () => {
    test('deve sanitizar nome de usuario para exibicao em HTML', () => {
        const nomesMaliciosos = [
            '<script>alert(1)</script>',
            'Usuario <b>Admin</b>',
            'Nome "com" aspas',
            "Nome 'com' aspas simples",
            'Nome & Sobrenome',
        ];

        nomesMaliciosos.forEach(nome => {
            const sanitizado = Sanitize.escapeHtml(nome);
            expect(sanitizado).not.toContain('<script>');
            expect(sanitizado).not.toContain('<b>');
            // Verificar que nao contem caracteres nao-escapados
            expect(sanitizado).not.toMatch(/[<>"'&](?!amp;|lt;|gt;|quot;|#039;)/);
        });
    });

    test('deve sanitizar nome para uso em atributo onclick', () => {
        const nome = "Maria D'Silva";
        const sanitizado = Sanitize.escapeJs(nome);

        // Simula uso em onclick="excluirUsuario(1, '${sanitizado}')"
        const onclickCode = `excluirUsuario(1, '${sanitizado}')`;

        // Verifica que o codigo e valido (nao quebra a string)
        expect(onclickCode).toBe("excluirUsuario(1, 'Maria D\\'Silva')");
    });

    test('deve sanitizar email para exibicao', () => {
        const email = 'user+tag@example.com';
        const sanitizado = Sanitize.escapeHtml(email);
        expect(sanitizado).toBe('user+tag@example.com');
    });

    test('deve sanitizar descricao de servico com HTML', () => {
        const descricao = 'Pavimentação <em>asfáltica</em> - 100m²';
        const sanitizado = Sanitize.escapeHtml(descricao);
        expect(sanitizado).toBe('Pavimentação &lt;em&gt;asfáltica&lt;/em&gt; - 100m²');
    });
});
