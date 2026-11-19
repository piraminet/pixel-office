FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --production
COPY . .
RUN mkdir -p /app/data
EXPOSE 19000
CMD ["node", "server.js"]
