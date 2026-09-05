# Explorar el histórico online o self-hosted

Decisión tomada de forma autónoma (sesión del 2026-09-05), a revisar por el
mantenedor. Objetivo: que cualquiera pueda explorar `impo_historico.parquet`
(616M+ filas, ~2 GB y creciendo) desde un link, sin que eso implique duplicar
los datos en una base de datos pesada ni pagar cómputo por cada consulta.

## Decisión: consultar el Parquet directamente, no importarlo a una base

Se descarta cargar el histórico a Postgres/Supabase como tabla. Motivos:

- **616M+ filas en un motor de fila (Postgres) es caro e innecesario**: el
  dato ya vive en un formato columnar comprimido (zstd) pensado exactamente
  para este tipo de consulta analítica. Reimportarlo a filas infla el tamaño
  en disco varias veces y no aporta nada que Parquet + DuckDB no den ya.
- **Habría que mantener el import sincronizado**: cada `--actualizar` tendría
  que reflejarse también en la base, con su propio pipeline de carga.
- **DuckDB puede leer Parquet remoto por HTTP Range requests** (extensión
  `httpfs`), pidiendo solo los row groups/columnas que la consulta necesita.
  Como el histórico está ordenado por `PERIODO, DESTINACION, NUM_ITEM,
  ARANCEL_CONCEPTO` (ver README), un filtro por rango de fechas poda la
  mayoría de los row groups gracias a las estadísticas min/max de Parquet,
  sin tocar el resto del archivo.

En cambio: **subir el Parquet a un object storage con soporte de Range
requests, y consultarlo desde ahí**, en dos capas que se pueden desplegar por
separado.

## Capa 1 (arrancar por acá): sitio estático + DuckDB-WASM

Todo el cómputo corre en el navegador de quien visita la página. Sin backend,
sin costo de cómputo del lado servidor, escala solo (cada visitante trae su
propia CPU).

```
Visitante
   |
   v
Pagina estatica (Vercel / Cloudflare Pages / GitHub Pages)
   |  carga duckdb-wasm (JS+WASM, via CDN)
   v
DuckDB corriendo en el navegador
   |  SELECT ... FROM read_parquet('https://.../impo_historico.parquet')
   |  (Range requests: solo baja los row groups que la consulta toca)
   v
Object storage con Range requests + CORS
(Supabase Storage / Cloudflare R2 / Backblaze B2 / GitHub Release asset)
```

- **Dónde alojar el Parquet**: cualquier object storage con acceso público de
  lectura, soporte de `Range` y headers CORS correctos. Supabase Storage
  encaja bien si de última se usa igual Supabase para otra cosa (auth,
  analytics propio); Cloudflare R2 tiene egress gratis, que importa si el
  archivo se descarga en pedazos muchas veces. Cualquiera de las dos sirve;
  no hace falta decidirlo ahora, `explorer/index.html` toma la URL por
  parámetro.
- **Dónde alojar la página**: Vercel (gratis para esto), Cloudflare Pages, o
  GitHub Pages. Es un HTML estático, no hay build step obligatorio.
- **Prototipo ya armado en el repo**: `explorer/index.html`. Es una pagina
  sola, sin dependencias de build, que carga `@duckdb/duckdb-wasm` desde CDN
  y deja correr SQL libre contra la URL del Parquet (configurable por query
  string `?data=` o editable en el archivo). Pensada como punto de partida,
  no como producto terminado: hoy es "una caja de SQL", falta UI para
  búsquedas guiadas (por importador, por NCM, por rango de fechas) si se
  quiere algo más amigable para quien no sabe SQL.

Limitaciones de esta capa: depende de que el navegador soporte WASM (todos
los navegadores modernos lo hacen) y de que el object storage exponga bien
Range + CORS. Consultas muy pesadas (un `GROUP BY` sobre las 616M de filas
sin ningún filtro) van a tardar y consumir la RAM del navegador de quien la
corre; no hay forma de evitar eso sin agregar la capa 2.

## Capa 2 (opcional, si hace falta más adelante): función serverless

Si en algún momento se quiere una UI más guiada (filtros con botones, no una
caja de SQL) o consultas pesadas que no conviene correr en el navegador de
cada visitante, se puede agregar una función serverless (Vercel Function o
Supabase Edge Function) que corra DuckDB del lado servidor contra el mismo
Parquet en el mismo object storage, y devuelva JSON ya armado. Esto sigue sin
duplicar el dato: la función lee el mismo archivo, no una copia en una base.
Se paga por invocación/tiempo de cómputo, así que tiene sentido agregarlo
recién si la Capa 1 se queda corta, no antes.

## Cómo desplegar esto de punta a punta (paso a paso, sin dar nada por sabido)

Nadie corrió estos pasos todavía (hacen falta cuentas/credenciales que esta
sesión no tiene), así que acá va la receta completa con comandos reales, no
solo la arquitectura. Se puede seguir sin IA. Ruta recomendada: **Cloudflare
R2** para el storage (10 GB gratis, y lo más importante, **egress gratis**:
no cobra por cuánto se descargue el archivo, que es justo lo que importa
acá porque cada consulta pide pedazos del mismo archivo muchas veces) +
**Cloudflare Pages** para la página estática (gratis, sin build).

### 1. Crear el bucket en Cloudflare R2

1. Crear una cuenta en <https://dash.cloudflare.com/sign-up> (gratis).
2. En el dashboard, ir a **R2 Object Storage** → **Create bucket**. Nombre
   sugerido: `comex-arca-historico`. Región: automática.
3. Instalar `wrangler` (CLI oficial de Cloudflare) si no está:
   ```powershell
   npm install -g wrangler
   wrangler login
   ```

### 2. Subir el Parquet

Desde la raíz del repo, con el histórico ya generado en `Data/impo_historico.parquet`:

```powershell
wrangler r2 object put comex-arca-historico/impo_historico.parquet --file Data\impo_historico.parquet
```

(Alternativa sin `wrangler`: R2 es compatible con la API de S3, así que
también funciona `aws s3 cp Data/impo_historico.parquet s3://comex-arca-historico/ --endpoint-url https://<ACCOUNT_ID>.r2.cloudflarestorage.com`
generando credenciales R2 en **R2 → Manage API tokens**.)

### 3. Hacerlo público y habilitar CORS + Range

1. En el bucket, **Settings → Public access → Allow Access** (esto genera una
   URL pública tipo `https://pub-xxxxxxxx.r2.dev/impo_historico.parquet`, o
   configurar un dominio propio en **Custom Domains** si se prefiere).
2. **Settings → CORS Policy**, agregar:
   ```json
   [
     {
       "AllowedOrigins": ["*"],
       "AllowedMethods": ["GET", "HEAD"],
       "AllowedHeaders": ["Range"],
       "ExposeHeaders": ["Content-Range", "Content-Length", "Accept-Ranges"]
     }
   ]
   ```
   (Range requests las sirve R2 automáticamente; esto solo habilita que un
   navegador en otro dominio pueda pedirlas.)
3. Confirmar que funciona: `curl -I https://pub-xxxxxxxx.r2.dev/impo_historico.parquet`
   debe mostrar `accept-ranges: bytes`.

### 4. Desplegar `explorer/index.html`

Con `wrangler` ya instalado:

```powershell
wrangler pages deploy explorer --project-name comex-arca-explorer
```

Esto imprime una URL tipo `https://comex-arca-explorer.pages.dev`. Abrirla,
pegar la URL pública del Parquet (paso 3) en el campo de arriba de la
página, y correr una consulta de prueba.

(Alternativa: Vercel o GitHub Pages sirven igual, `explorer/index.html` no
tiene nada específico de Cloudflare. Con Vercel: `npx vercel deploy explorer --prod`.)

### 5. Fijar la URL por defecto (para no tener que pegarla cada vez)

Editar `explorer/index.html`, buscar `dataUrlEl.value = defaultDataUrl();` y
agregar un valor por defecto:

```js
dataUrlEl.value = defaultDataUrl() || "https://pub-xxxxxxxx.r2.dev/impo_historico.parquet";
```

Volver a desplegar (paso 4) para que quede fijo.

## Actualizar el archivo publicado

Cuando corre `--actualizar` y cambia `impo_historico.parquet` localmente, hay
que volver a subirlo (reemplaza el anterior, mismo nombre):

```powershell
wrangler r2 object put comex-arca-historico/impo_historico.parquet --file Data\impo_historico.parquet
```

Esto todavía no está integrado a la skill `actualizar-historico-arca`
(`.claude/skills/actualizar-historico-arca/SKILL.md`) porque depende del
bucket que cada quien haya creado en el paso 1; una vez que el nombre del
bucket esté decidido, conviene agregar este comando como paso final de la
skill.

## Qué falta para que esto sea un producto real

La arquitectura y el prototipo están listos y probados (`explorer/index.html`
corre localmente contra cualquier Parquet accesible por HTTP); lo que falta
es específicamente ejecutar los pasos 1-5 de arriba, que requieren una cuenta
de Cloudflare (u otro proveedor) que esta sesión no tiene. Después de eso:

1. Decidir si hace falta la Capa 2 (función serverless) y con qué UI, si la
   "caja de SQL" no alcanza para el público que se busca.
2. Si el tráfico crece mucho, revisar límites del plan gratis elegido (R2:
   10 GB de storage y sin límite de egress en el plan gratis al momento de
   escribir esto; confirmar en la página de precios del proveedor antes de
   depender de esto para algo con tráfico real).
