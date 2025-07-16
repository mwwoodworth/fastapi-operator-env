/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $Body_auth_token_auth_token_post = {
    properties: {
        grant_type: {
            type: 'any-of',
            contains: [{
                type: 'string',
                pattern: '^password$',
            }, {
                type: 'null',
            }],
        },
        username: {
            type: 'string',
            isRequired: true,
        },
        password: {
            type: 'string',
            isRequired: true,
            format: 'password',
        },
        scope: {
            type: 'string',
        },
        client_id: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'null',
            }],
        },
        client_secret: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'null',
            }],
        },
    },
} as const;
