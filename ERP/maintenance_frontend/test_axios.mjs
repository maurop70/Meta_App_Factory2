import axios from 'axios';
const API_BASE_URL = '/api';
const apiClient = axios.create({ baseURL: API_BASE_URL });
console.log(apiClient.getUri({ url: '/api/mwo' }));
console.log(apiClient.getUri({ url: '/user/authenticate' }));
console.log(apiClient.getUri({ url: 'api/mwo' }));
