FROM tiangolo/meinheld-gunicorn-flask:python3.8-alpine3.11
COPY . /app
WORKDIR /app

RUN apk add --no-cache \
    build-base cairo-dev cairo cairo-tools \
    # pillow dependencies
    jpeg-dev zlib-dev freetype-dev lcms2-dev openjpeg-dev tiff-dev tk-dev tcl-dev

# Install Google Fonts
RUN apk add --no-cache msttcorefonts-installer fontconfig
RUN update-ms-fonts
RUN wget https://github.com/google/fonts/archive/master.tar.gz -O gf.tar.gz --no-check-certificate
RUN tar -xf gf.tar.gz
RUN mkdir -p /usr/share/fonts/truetype/google-fonts
RUN find $PWD/fonts-master/ -name "*.ttf" -exec install -m644 {} /usr/share/fonts/truetype/google-fonts/ \; || return 1
RUN rm -f gf.tar.gz
RUN fc-cache -f && rm -rf /var/cache/*

RUN pip install -r requirements.txt
