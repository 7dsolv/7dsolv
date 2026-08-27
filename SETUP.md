# Publicação do perfil `7dsolv`

Este pacote foi preparado para o repositório especial `7dsolv/7dsolv`. O GitHub mostra o `README.md` desse repositório na página principal do perfil.

## Opção recomendada: enviar a pasta inteira

1. Abra <https://github.com/7dsolv/7dsolv>.
2. Se o editor do `README.md` estiver aberto, cancele a edição.
3. Clique em **Add file → Upload files**.
4. Arraste **todo o conteúdo** desta pasta `github-profile` para a página, preservando:

   ```text
   README.md
   assets/
   publications/
   scripts/
   .github/workflows/
   ```

5. Use a mensagem `feat: criar perfil cyberpunk completo` e confirme o commit na branch `principal`.
6. Abra **Settings → Actions → General → Workflow permissions**, selecione **Read and write permissions** e salve.
7. Abra **Actions → Atualizar perfil → Run workflow** para gerar as métricas imediatamente.

## Se o GitHub não aceitar pastas pelo navegador

Use Git no PowerShell:

```powershell
git clone https://github.com/7dsolv/7dsolv.git
Copy-Item -LiteralPath "C:\Users\PC\Desktop\Konaet OS\github-profile\README.md" -Destination ".\7dsolv\README.md" -Force
Copy-Item -LiteralPath "C:\Users\PC\Desktop\Konaet OS\github-profile\assets" -Destination ".\7dsolv" -Recurse -Force
Copy-Item -LiteralPath "C:\Users\PC\Desktop\Konaet OS\github-profile\publications" -Destination ".\7dsolv" -Recurse -Force
Copy-Item -LiteralPath "C:\Users\PC\Desktop\Konaet OS\github-profile\scripts" -Destination ".\7dsolv" -Recurse -Force
Copy-Item -LiteralPath "C:\Users\PC\Desktop\Konaet OS\github-profile\.github" -Destination ".\7dsolv" -Recurse -Force
Set-Location .\7dsolv
git add README.md assets publications scripts .github
git commit -m "feat: criar perfil cyberpunk completo"
git push origin principal
```

> Se o Git informar que sua branch se chama `main`, troque apenas o último comando por `git push origin main`.

## Personalização rápida

- Links e textos principais: `README.md`
- Cabeçalho: `assets/header.svg`
- Terminal: `assets/terminal.svg`
- Rodapé: `assets/footer.svg`
- PDFs publicados: `publications/`
- Métricas automáticas: `scripts/generate_profile_assets.py`

Não cole os arquivos SVG diretamente dentro do `README.md`. O GitHub remove animações e partes do CSS de SVG inline por segurança. Como arquivos em `assets/`, eles renderizam corretamente.

## Liberar o Google Drive para visitantes

O link informado foi testado e responde publicamente. Se no futuro o acesso parar de funcionar, confira no Google Drive:

1. Clique com o botão direito na pasta `Engenharia.7dsolv`.
2. Abra **Compartilhar**.
3. Em **Acesso geral**, troque para **Qualquer pessoa com o link**.
4. Mantenha a função **Leitor** e clique em **Copiar link**.
5. Se o link copiado for diferente, substitua as duas ocorrências atuais de `drive.google.com` no `README.md`.

O GitHub não permite incorporar o leitor do Google Drive com `iframe`. Por isso, o perfil mostra as capas na tela inicial e abre o PDF completo ao clique — a forma compatível e segura de obter o mesmo efeito.
