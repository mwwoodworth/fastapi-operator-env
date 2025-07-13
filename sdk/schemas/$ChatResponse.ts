/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $ChatResponse = {
    properties: {
        response: {
            type: 'string',
            isRequired: true,
        },
        model: {
            type: 'string',
            isRequired: true,
        },
        suggested_tasks: {
            type: 'any-of',
            contains: [{
                type: 'null',
            }],
        },
        memory_id: {
            type: 'string',
            isRequired: true,
        },
    },
} as const;
