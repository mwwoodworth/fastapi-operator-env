/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $PageUpdatePayload = {
    properties: {
        token: {
            type: 'string',
            isRequired: true,
        },
        workspace: {
            type: 'string',
            isRequired: true,
        },
        properties: {
            type: 'dictionary',
            contains: {
                properties: {
                },
            },
            isRequired: true,
        },
        idempotency_key: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'null',
            }],
        },
    },
} as const;
