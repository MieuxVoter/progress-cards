FROM tiangolo/meinheld-gunicorn-flask:python3.8-alpine3.11
COPY . /app
WORKDIR /app

RUN apk add --no-cache \
    build-base cairo-dev cairo cairo-tools \
    # pillow dependencies
    jpeg-dev zlib-dev freetype-dev lcms2-dev openjpeg-dev tiff-dev tk-dev tcl-dev

RUN pip install -r requirements.txt

