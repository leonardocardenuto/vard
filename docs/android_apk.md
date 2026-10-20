# APK Android para teste no celular

O APK de instalação contém o JavaScript e os módulos nativos. Ele abre sem
Metro, Expo Go ou computador servindo o bundle. A API e a inferência de câmera
continuam no computador; mantenha a API e o monitor ligado para testar novas
ocorrências. O telefone precisa alcançar o endereço da API pela rede.

Este build usa `http://172.19.190.206:8000`, conforme os arquivos de ambiente
do app. Se o IP da API mudar, atualize o ambiente e gere outro APK. A câmera
tem seu próprio IP cadastrado no banco, independente do endereço da API.

O arquivo é compilado em release para Android ARM64 e assinado com a chave
de desenvolvimento existente, para instalação e testes pessoais. O perfil
`preview` do EAS também está configurado para produzir APK. A distribuição
pela Play Store precisa de assinatura e configuração próprias.

## Build local usado neste Mac

Na pasta `app`, sincronize o projeto Android:

```bash
npx expo prebuild --platform android --no-install
```

Na pasta `app/android`:

```bash
JAVA_HOME='/Applications/Android Studio.app/Contents/jbr/Contents/Home' \
ANDROID_HOME="$HOME/Library/Android/sdk" \
GRADLE_USER_HOME="$PWD/../.gradle-local" \
./gradlew :app:assembleRelease -PreactNativeArchitectures=arm64-v8a \
  --console=plain --max-workers=4
```

Saída: `app/android/app/build/outputs/apk/release/app-release.apk`.
O plugin local mantém HTTP habilitado no manifesto de release para os
endereços da API e das câmeras locais usados neste ambiente de teste.

No celular, baixe o APK, permita a instalação pelo navegador/gerenciador
de arquivos quando o Android pedir e autorize notificações ao abrir o app.
