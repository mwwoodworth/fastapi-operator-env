/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $DelayRequest = {
    properties: {
        task_id: {
            type: 'string',
            isRequired: true,
        },
        delay_until: {
            type: 'string',
            isRequired: true,
        },
        note: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'null',
            }],
        },
        fallback: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'null',
            }],
        },
    },
} as const;
